from __future__ import annotations
from app.core.financial_rules import emergency_shortfall

import random
import statistics
from typing import Any, Dict, List, Optional

from app.core.simulation import simulate_finance


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * pct
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def run_monte_carlo(
    profile: Dict[str, Any],
    base_events: Optional[List[Dict[str, Any]]] = None,
    loans: Optional[List[Dict[str, Any]]] = None,
    random_shocks: Optional[List[Dict[str, Any]]] = None,
    months: int = 60,
    simulations: int = 500,
    seed: Optional[int] = None,
    sample_paths: int = 8,
    include_details: bool = False,
) -> Dict[str, Any]:
    if months <= 0:
        raise ValueError("months must be > 0")
    if simulations <= 0 or simulations > 5000:
        raise ValueError("simulations must be between 1 and 5000")

    base_events = base_events or []
    loans = loans or []
    random_shocks = random_shocks or []
    master_rng = random.Random(seed)

    final_balances: List[float] = []
    cash_shortfall_count = 0
    emergency_shortfalls: List[float] = []
    paths = []
    debug_paths = []

    for index in range(simulations):
        path_seed = master_rng.randint(0, 2_147_483_647)
        sampled_raise_rate = master_rng.uniform(0.01, 0.06)
        sampled_inflation_rate = master_rng.uniform(0.01, 0.05)
        result = simulate_finance(
            profile=profile,
            months=months,
            events=base_events,
            loans=loans,
            random_shocks=random_shocks,
            seed=path_seed,
            include_details=include_details,
            override_raise_rate=sampled_raise_rate,
            override_inflation_rate=sampled_inflation_rate,
        )
        summary = result["summary"]
        curve = result["simulation_curve"]
        final_balances.append(summary["final_balance"])
        cash_shortfall_count += summary["first_negative_cash_month"] is not None
        target_months = float(profile.get("target_emergency_months", 3))
        emergency_shortfalls.append(emergency_shortfall(summary["final_balance"], curve[-1]["living_expense"], curve[-1]["debt_payment"], target_months))
        if index < sample_paths:
            paths.append(
                {
                    "seed": path_seed,
                    "points": [{"month": row["month"], "balance": row["balance"]} for row in curve],
                }
            )
        if include_details and index < min(3, sample_paths):
            debug_paths.append(result)

    shortfall_probability = cash_shortfall_count / simulations

    response = {
        "iterations": simulations,
        "seed": seed,
        "avg_final_balance": round(statistics.fmean(final_balances), 2),
        "median_final_balance": round(statistics.median(final_balances), 2),
        "min_final_balance": round(min(final_balances), 2),
        "max_final_balance": round(max(final_balances), 2),
        "percentiles": {
            "p5": round(percentile(final_balances, 0.05), 2),
            "p25": round(percentile(final_balances, 0.25), 2),
            "p50": round(percentile(final_balances, 0.50), 2),
            "p75": round(percentile(final_balances, 0.75), 2),
            "p95": round(percentile(final_balances, 0.95), 2),
        },
        "probability_cash_shortfall": round(shortfall_probability, 4),
        "cash_shortfall_definition": "模擬期間任一月底現金小於 0 的試驗比例",
        "expected_emergency_fund_shortfall": round(statistics.fmean(emergency_shortfalls), 2),
        "sample_paths": paths,
    }
    if include_details:
        response["debug_paths"] = debug_paths
    return response
