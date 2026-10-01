from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from app.core.events import (
    debt_to_income_for_month,
    get_debt_payment_for_month,
    get_fixed_expense_for_month,
    get_income_for_month,
    get_one_time_asset_impact,
    get_recurring_event_amount,
)
from app.core.expenses import calculate_variable_expenses
from app.core.fsi import calculate_fsi, classify_risk
from app.core.shocks import generate_shocks_for_month
from app.core.financial_rules import emergency_fund_months, inflation_factor


def summarize_simulation(simulation_curve: List[Dict[str, Any]], profile: Dict[str, Any]) -> Dict[str, Any]:
    if not simulation_curve:
        return {
            "final_balance": 0.0,
            "min_balance": 0.0,
            "max_fsi": 0.0,
            "avg_fsi": 0.0,
            "high_risk_months": 0,
            "first_risk_month": None,
            "emergency_fund_coverage": 0.0,
            "debt_to_income": 0.0,
        }

    final_balance = simulation_curve[-1]["balance"]
    min_balance = min(item["balance"] for item in simulation_curve)
    max_fsi = max(item["fsi"] for item in simulation_curve)
    avg_fsi = sum(item["fsi"] for item in simulation_curve) / len(simulation_curve)
    high_risk_months = [item["month"] for item in simulation_curve if item["risk_level"] in ("high", "crisis")]
    final = simulation_curve[-1]
    coverage = emergency_fund_months(final_balance, final.get("living_expense", final["expense"]), final["debt_payment"])
    emergency_fund_coverage = coverage if coverage is not None else 0.0
    coverages = [r["emergency_fund_months"] for r in simulation_curve if r.get("emergency_fund_months") is not None]

    return {
        "final_balance": round(final_balance, 2),
        "min_balance": round(min_balance, 2),
        "minimum_cash_balance": round(min_balance, 2),
        "minimum_cash_month": min(simulation_curve, key=lambda r: r["balance"])["month"],
        "minimum_emergency_fund_months": round(min(coverages), 4) if coverages else None,
        "max_fsi": round(max_fsi, 4),
        "avg_fsi": round(avg_fsi, 4),
        "high_risk_months": len(high_risk_months),
        "first_risk_month": high_risk_months[0] if high_risk_months else None,
        "emergency_fund_coverage": round(emergency_fund_coverage, 2),
        "debt_to_income": simulation_curve[-1]["debt_to_income"],
        "risk_level": classify_risk(max_fsi, min_balance),
        "target_emergency_months": profile.get("target_emergency_months", 3),
    }


def simulate_finance(
    profile: Dict[str, Any],
    months: int = 60,
    events: Optional[List[Dict[str, Any]]] = None,
    loans: Optional[List[Dict[str, Any]]] = None,
    random_shocks: Optional[List[Dict[str, Any]]] = None,
    seed: Optional[int] = None,
    include_details: bool = False,
    override_raise_rate: Optional[float] = None,
    override_inflation_rate: Optional[float] = None,
    evaluate_legacy_risk: bool = True,
) -> Dict[str, Any]:
    if months <= 0:
        raise ValueError("months must be > 0")

    events = events or []
    loans = loans or []
    random_shocks = random_shocks or []
    rng = random.Random(seed)

    base_salary = float(profile["salary"])
    base_fixed_expense = float(profile["fixed_expense"])
    balance = float(profile["balance"])
    raise_rate = float(override_raise_rate if override_raise_rate is not None else profile.get("raise_rate", 0.03))
    inflation_rate = float(override_inflation_rate if override_inflation_rate is not None else profile.get("inflation_rate", 0.02))
    target_emergency_months = float(profile.get("target_emergency_months", 3))

    profile = {**profile, "inflation_rate": inflation_rate}
    curve: List[Dict[str, Any]] = []
    shock_details: List[Dict[str, Any]] = []

    for month in range(1, months + 1):
        years_passed = (month - 1) // 12
        scheduled_income = base_salary * ((1 + raise_rate) ** years_passed)
        income = get_income_for_month(month, scheduled_income, events)
        fixed_base = base_fixed_expense * (inflation_factor(month, inflation_rate) if profile.get("fixed_expense_inflates", False) else 1)
        fixed_expense = get_fixed_expense_for_month(month, fixed_base, events)
        variable_result = calculate_variable_expenses(
            month=month,
            profile=profile,
            income=income,
            base_income=max(base_salary, 1.0),
            events=events,
            rng=rng,
        )
        debt_payment = get_debt_payment_for_month(month, loans) + float(profile.get("required_monthly_debt", 0))
        recurring_event_amount = get_recurring_event_amount(month, events)
        living_expense = max(0.0, fixed_expense + variable_result["total"] - recurring_event_amount)
        one_time_asset_impact = get_one_time_asset_impact(month, events)
        shock_result = generate_shocks_for_month(
            month=month,
            random_shocks=random_shocks,
            rng=rng,
            include_details=include_details,
        )
        shock_expense = shock_result["total"]
        shock_details.extend(shock_result["details"])

        total_expense = fixed_expense + variable_result["total"] + debt_payment + shock_expense
        net_cashflow = income - total_expense + recurring_event_amount + one_time_asset_impact
        balance += net_cashflow

        fsi = calculate_fsi(
            income=income,
            expense=living_expense,
            debt_payment=debt_payment,
            balance=balance,
            target_emergency_months=target_emergency_months,
        ) if evaluate_legacy_risk else 0.0
        risk_level = classify_risk(fsi, balance) if evaluate_legacy_risk else None

        row = {
            "month": month,
            "income": round(income, 2),
            "fixed_expense": round(fixed_expense, 2),
            "variable_expense": variable_result["total"],
            "expense": round(fixed_expense + variable_result["total"] + shock_expense, 2),
            "debt_payment": round(debt_payment, 2),
            "living_expense": round(living_expense, 2),
            "emergency_fund_months": emergency_fund_months(balance, living_expense, debt_payment),
            "shock_expense": shock_expense,
            "event_net": round(recurring_event_amount + one_time_asset_impact, 2),
            "net_cashflow": round(net_cashflow, 2),
            "balance": round(balance, 2),
            "fsi": round(fsi, 4),
            "risk_level": risk_level,
            "debt_to_income": debt_to_income_for_month(month, income, loans),
        }
        if include_details:
            row["expense_categories"] = variable_result["categories"]
        curve.append(row)

    result = {
        "simulation_curve": curve,
        "summary": summarize_simulation(curve, profile) if evaluate_legacy_risk else {},
        "seed": seed,
    }
    if include_details:
        result["shock_details"] = shock_details
    return result
