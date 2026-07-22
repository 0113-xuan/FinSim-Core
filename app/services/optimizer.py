from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from app.core.advisor import compare_options


BASELINE_OPTION_NAME = "Baseline"


def find_baseline_option(options: List[Dict[str, Any]]) -> Dict[str, Any]:
    matches = [
        option
        for option in options
        if option.get("name") == BASELINE_OPTION_NAME
    ]
    if not matches:
        raise ValueError("Optimization comparison is missing the baseline option")
    if len(matches) > 1:
        raise ValueError("Optimization comparison contains multiple baseline options")
    return matches[0]


def _violations(summary: Dict[str, Any], mc: Dict[str, Any], constraints: Dict[str, Any]) -> List[str]:
    issues = []
    if constraints.get("balance_must_not_be_negative") and summary["min_balance"] < 0:
        issues.append("Balance becomes negative")
    if constraints.get("maximum_fsi_below") is not None and summary["max_fsi"] >= constraints["maximum_fsi_below"]:
        issues.append("Maximum FSI exceeds constraint")
    if constraints.get("bankruptcy_probability_below") is not None and mc["bankrupt_probability"] >= constraints["bankruptcy_probability_below"]:
        issues.append("Bankruptcy probability exceeds constraint")
    if constraints.get("minimum_emergency_months_above") is not None and summary["emergency_fund_coverage"] < constraints["minimum_emergency_months_above"]:
        issues.append("Emergency fund coverage is too low")
    if constraints.get("debt_to_income_below") is not None and summary["debt_to_income"] >= constraints["debt_to_income_below"]:
        issues.append("Debt-to-income ratio is too high")
    return issues


def optimize(request: Dict[str, Any]) -> Dict[str, Any]:
    profile = request["profile"]
    constraints = request.get("constraints", {})
    max_candidates = request.get("max_candidates", 24)
    candidates = [{"name": BASELINE_OPTION_NAME}]

    for pct in [0.05, 0.1, 0.15, 0.2]:
        updated = deepcopy(profile)
        updated["variable_expense"] = round(updated.get("variable_expense", 0) * (1 - pct), 2)
        if updated.get("variable_expense_model", {}).get("mode") == "quick":
            updated["variable_expense_model"]["total_variable_expense"] = updated["variable_expense"]
        candidates.append({"name": f"Reduce variable expenses {int(pct * 100)}%", "profile_overrides": updated})

    for pct in [0.05, 0.1, 0.15]:
        updated = deepcopy(profile)
        updated["salary"] = round(updated.get("salary", 0) * (1 + pct), 2)
        candidates.append({"name": f"Increase income {int(pct * 100)}%", "profile_overrides": updated})

    candidates = candidates[:max_candidates]
    comparison = compare_options(profile, candidates, months=request.get("months", 60), mc_runs=120, seed=request.get("seed"))
    feasible = []
    rejected = []
    for option in comparison["options"]:
        issues = _violations(option["simulation_summary"], option["monte_carlo_summary"], constraints)
        if issues:
            rejected.append({"name": option["name"], "violations": issues, "score": option["score"]})
        else:
            feasible.append(option)
    best = feasible[0] if feasible else comparison["options"][0]
    baseline = find_baseline_option(comparison["options"])
    return {
        "best_scenario": best,
        "feasible_scenarios": feasible,
        "rejected_scenarios": rejected,
        "baseline": baseline,
        "explanation": f"Recommended option is {best['name']} based on deterministic scoring and constraints.",
    }
