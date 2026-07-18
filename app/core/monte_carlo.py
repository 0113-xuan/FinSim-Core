from __future__ import annotations

import random
import statistics
from collections import Counter
from typing import Any, Dict, List, Optional

from app.core.fsi import classify_risk
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
    min_balances: List[float] = []
    max_fsis: List[float] = []
    emergency_shortfalls: List[float] = []
    high_risk_month_counter: Counter[int] = Counter()
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
        min_balances.append(summary["min_balance"])
        max_fsis.append(summary["max_fsi"])
        target_months = float(profile.get("target_emergency_months", 3))
        final_expense = max(1.0, curve[-1]["expense"] + curve[-1]["debt_payment"])
        emergency_shortfalls.append(max(0.0, target_months * final_expense - summary["final_balance"]))
        for row in curve:
            if row["risk_level"] in ("high", "crisis"):
                high_risk_month_counter[row["month"]] += 1
        if index < sample_paths:
            paths.append(
                {
                    "seed": path_seed,
                    "points": [{"month": row["month"], "balance": row["balance"], "fsi": row["fsi"]} for row in curve],
                }
            )
        if include_details and index < min(3, sample_paths):
            debug_paths.append(result)

    negative_probability = sum(1 for value in min_balances if value < 0) / simulations
    bankruptcy_probability = sum(1 for value in final_balances if value < 0) / simulations
    avg_max_fsi = statistics.fmean(max_fsis)
    risk_level = classify_risk(avg_max_fsi, min(min_balances))

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
        "probability_negative_balance": round(negative_probability, 4),
        "bankrupt_probability": round(bankruptcy_probability, 4),
        "avg_max_fsi": round(avg_max_fsi, 4),
        "high_risk_month_distribution": [
            {"month": month, "frequency": count, "probability": round(count / simulations, 4)}
            for month, count in sorted(high_risk_month_counter.items())
        ],
        "expected_emergency_fund_shortfall": round(statistics.fmean(emergency_shortfalls), 2),
        "sample_paths": paths,
        "risk_classification": risk_level,
    }
    if include_details:
        response["debug_paths"] = debug_paths
    return response
