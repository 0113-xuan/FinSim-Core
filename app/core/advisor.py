from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from app.core.monte_carlo import run_monte_carlo
from app.core.simulation import simulate_finance


def _merge_profile(profile: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(profile)
    for key, value in overrides.items():
        if key in merged:
            merged[key] = value
    return merged


def compare_options(
    profile: Dict[str, Any],
    options: List[Dict[str, Any]],
    months: int = 60,
    mc_runs: int = 300,
    seed: int | None = None,
) -> Dict[str, Any]:
    if not options:
        raise ValueError("options must not be empty")

    option_results = []
    for index, option in enumerate(options):
        option_profile = _merge_profile(profile, option.get("profile_overrides", {}))
        sim_result = simulate_finance(
            profile=option_profile,
            months=months,
            events=option.get("events", []),
            loans=option.get("loans", []),
            random_shocks=option.get("random_shocks", []),
            seed=seed,
        )
        mc_result = run_monte_carlo(
            profile=option_profile,
            base_events=option.get("events", []),
            loans=option.get("loans", []),
            random_shocks=option.get("random_shocks", []),
            months=months,
            simulations=mc_runs,
            seed=None if seed is None else seed + index,
            sample_paths=4,
        )
        option_results.append(
            {
                "name": option["name"],
                "simulation_summary": sim_result["summary"],
                "monte_carlo_summary": mc_result,
            }
        )

    option_results.sort(key=lambda item: (
        item["monte_carlo_summary"]["probability_cash_shortfall"],
        -item["monte_carlo_summary"]["median_final_balance"],
    ))
    return {"best_option": option_results[0]["name"], "options": option_results,
            "sorting_rule": "現金不足機率由低到高，再依期末現金中位數由高到低"}


def generate_advice(compare_result: Dict[str, Any]) -> Dict[str, Any]:
    best = compare_result["options"][0]
    sim = best["simulation_summary"]
    mc = best["monte_carlo_summary"]
    suggestions = []
    if sim["min_balance"] < 0:
        suggestions.append("優先降低一次性支出或延後事件時程，避免資產在期間內跌破零。")
    if mc["probability_cash_shortfall"] >= 0.1:
        suggestions.append("Monte Carlo 顯示現金不足機率偏高，請增加收入緩衝或縮小貸款規模。")
    if not suggestions:
        suggestions.append("目前方案風險可控，可持續追蹤支出分類與重大生活事件。")
    return {
        "summary": f"根據 deterministic simulation 與 Monte Carlo，建議方案為「{best['name']}」。",
        "best_option": best["name"],
        "reason": [
            f"最低資產：{sim['min_balance']}",
            f"現金不足機率：{mc['probability_cash_shortfall'] * 100:.2f}%",
        ],
        "suggestions": suggestions,
    }
