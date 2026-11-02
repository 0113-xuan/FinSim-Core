from fastapi.testclient import TestClient

from app.core.market_data import load_market_history
from app.core.monte_carlo import run_monte_carlo
from app.core.simulation import simulate_finance
from main import app

PROFILE = {
    "salary": 60000, "fixed_expense": 20000, "variable_expense": 10000, "balance": 900000,
    "investment_value": 500000, "monthly_investment": 3000,
}


def test_monthly_bands_cover_every_month_and_are_ordered():
    result = run_monte_carlo(PROFILE, months=60, simulations=80, seed=7, sample_paths=0)
    bands = result["monthly_bands"]
    assert bands["months"] == list(range(1, 61))
    for series, points in (("net_worth", ("p5", "p25", "p50", "p75", "p95")),
                           ("cash", ("p5", "p50", "p95")), ("investment", ("p5", "p50", "p95"))):
        assert set(bands[series]) == set(points)
        for values in bands[series].values():
            assert len(values) == 60
        for month in range(60):
            column = [bands[series][point][month] for point in points]
            assert column == sorted(column)


def test_last_month_band_matches_ending_percentiles():
    result = run_monte_carlo(PROFILE, months=36, simulations=60, seed=3, sample_paths=0)
    bands = result["monthly_bands"]
    for point in ("p5", "p25", "p50", "p75", "p95"):
        assert bands["net_worth"][point][-1] == result["net_worth_percentiles"][point]
    for point in ("p5", "p50", "p95"):
        assert bands["cash"][point][-1] == result["percentiles"][point]


def test_bands_do_not_change_existing_monte_carlo_numbers():
    with_bands = run_monte_carlo(PROFILE, months=24, simulations=40, seed=11, sample_paths=2)
    again = run_monte_carlo(PROFILE, months=24, simulations=40, seed=11, sample_paths=2)
    assert with_bands == again
    history = load_market_history()
    assert with_bands["historical_averages"] == {
        "annual_inflation_rate": round(history.annual_inflation_rate, 6),
        "annual_return_rate": round(history.annual_return_rate, 6),
    }


def test_deterministic_assumptions_disclose_historical_defaults():
    history = load_market_history()
    assumptions = simulate_finance(PROFILE, months=12)["assumptions"]
    assert assumptions == {
        "annual_inflation_rate": round(history.annual_inflation_rate, 6), "inflation_source": "historical_average",
        "raise_rate": None, "raise_source": "follows_inflation",
        "annual_return_rate": round(history.annual_return_rate, 6), "return_source": "historical_average",
    }


def test_deterministic_assumptions_disclose_user_rates():
    profile = {**PROFILE, "inflation_rate": 0.02, "raise_rate": 0.03, "expected_annual_return": 0.05}
    assumptions = simulate_finance(profile, months=12)["assumptions"]
    assert assumptions["annual_inflation_rate"] == 0.02 and assumptions["inflation_source"] == "user"
    assert assumptions["raise_rate"] == 0.03 and assumptions["raise_source"] == "user"
    assert assumptions["annual_return_rate"] == 0.05 and assumptions["return_source"] == "user"


def test_no_investment_means_no_return_rate():
    profile = {**PROFILE, "investment_value": 0, "monthly_investment": 0}
    assert simulate_finance(profile, months=12)["assumptions"]["annual_return_rate"] is None


def test_endpoints_return_bands_and_assumptions():
    client = TestClient(app)
    body = {"profile": {**PROFILE}, "months": 24, "seed": 42}
    simulated = client.post("/simulate", json=body).json()["result"]
    assert simulated["assumptions"]["inflation_source"] == "historical_average"
    mc = client.post("/monte-carlo", json={**body, "simulations": 30}).json()
    assert len(mc["monthly_bands"]["net_worth"]["p50"]) == 24
