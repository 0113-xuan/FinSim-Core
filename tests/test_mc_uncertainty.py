import random

import pytest
from fastapi.testclient import TestClient

from app.core import monte_carlo
from app.core.market_data import load_market_history
from app.core.mc_uncertainty import quantile_interval, wilson_interval
from main import app

PROFILE = {"salary": 60000, "fixed_expense": 20000, "variable_expense": 12000, "balance": 900000}
FIELDS = {"probability_cash_shortfall_interval", "net_worth_percentile_intervals", "uncertainty_note"}


def test_wilson_examples_and_properties():
    assert wilson_interval(0, 500) == pytest.approx((0, 0.00762462), abs=1e-4)
    assert wilson_interval(50, 500) == pytest.approx((0.07667719, 0.12942251), abs=1e-4)
    for successes in (0, 50, 250, 500):
        low, high = wilson_interval(successes, 500)
        assert low <= successes / 500 <= high
    small = wilson_interval(50, 500)
    large = wilson_interval(500, 5000)
    assert large[1] - large[0] < small[1] - small[0]
    with pytest.raises(ValueError):
        wilson_interval(0, 0)


def test_quantile_coverage():
    rng = random.Random(42)
    covered = 0
    for _ in range(400):
        values = [rng.random() for _ in range(500)]
        low, high = quantile_interval(values, .5)
        assert low <= monte_carlo.percentile(values, .5) <= high
        covered += low <= .5 <= high
    assert covered >= 360


def test_monte_carlo_fields_and_blocks(monkeypatch):
    args = dict(profile=PROFILE, months=13, simulations=10, seed=42)
    default = monte_carlo.run_monte_carlo(**args)
    assert default == monte_carlo.run_monte_carlo(**args, block_months=12)
    assert FIELDS <= default.keys()
    interval = default["probability_cash_shortfall_interval"]
    assert interval["low"] <= interval["high"] and interval["confidence"] == .95
    for pair in default["net_worth_percentile_intervals"].values():
        assert isinstance(pair, list) and len(pair) == 2 and pair[0] <= pair[1]
    assert isinstance(default["uncertainty_note"], str)
    draws = []
    original = monte_carlo.block_bootstrap_indices
    def record(*args):
        result = original(*args)
        draws.append(result)
        return result
    monkeypatch.setattr(monte_carlo, "block_bootstrap_indices", record)
    result = monte_carlo.run_monte_carlo(**args, block_months=6)
    assert result["sampling_method"]["block_months"] == 6
    for draw in draws:
        for start in (0, 6):
            assert draw[start:start + 6] == list(range(draw[start], draw[start] + 6))
    for bad in (0, -1, len(load_market_history().periods) + 1):
        with pytest.raises(ValueError):
            monte_carlo.run_monte_carlo(**args, block_months=bad)


def test_endpoint_returns_intervals():
    response = TestClient(app).post("/monte-carlo", json={"profile": PROFILE, "months": 12, "simulations": 10, "seed": 42})
    assert response.status_code == 200
    assert FIELDS <= response.json().keys()



def test_history_length_matches_knowledge():
    from pathlib import Path
    history = load_market_history()
    assert (history.start_period, history.end_period, len(history.periods)) == ("2003-02", "2026-09", 284)
    text = (Path(__file__).resolve().parents[1] / "data/knowledge/limits.md").read_text(encoding="utf-8")
    section = text.split("id: history-length", 1)[1].split("\n## ", 1)[0]
    assert all(value in section for value in (history.start_period, history.end_period, str(len(history.periods))))
