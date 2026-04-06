# simulation.py
from typing import Dict, List, Any, Optional
from fsi import calculate_fsi, classify_risk
from events import get_monthly_event_net, get_salary_for_month, get_debt_payment_for_month


def monthly_income(base_salary: float, raise_rate: float, month: int) -> float:
    """
    月收入模型：每年成長一次的簡化版本
    """
    years_passed = (month - 1) // 12
    income = base_salary * ((1 + raise_rate) ** years_passed)
    return round(income, 2)


def monthly_expense(fixed_expense: float, variable_expense: float, inflation_rate: float, month: int) -> float:
    """
    月支出模型：固定支出 + 變動支出逐年通膨成長
    """
    years_passed = (month - 1) // 12
    variable = variable_expense * ((1 + inflation_rate) ** years_passed)
    expense = fixed_expense + variable
    return round(expense, 2)


def summarize_simulation(simulation_curve: List[Dict[str, Any]]) -> Dict[str, Any]:
    final_balance = simulation_curve[-1]["balance"] if simulation_curve else 0
    min_balance = min(item["balance"] for item in simulation_curve) if simulation_curve else 0
    max_fsi = max(item["fsi"] for item in simulation_curve) if simulation_curve else 0
    avg_fsi = round(sum(item["fsi"] for item in simulation_curve) / len(simulation_curve), 4) if simulation_curve else 0

    high_risk_months = sum(1 for item in simulation_curve if item["risk_level"] in ("high", "crisis"))
    first_risk_month = next((item["month"] for item in simulation_curve if item["risk_level"] in ("high", "crisis")), None)

    return {
        "final_balance": round(final_balance, 2),
        "min_balance": round(min_balance, 2),
        "max_fsi": round(max_fsi, 4),
        "avg_fsi": avg_fsi,
        "high_risk_months": high_risk_months,
        "first_risk_month": first_risk_month
    }


def simulate_finance(
    profile: Dict[str, Any],
    months: int = 60,
    events: Optional[List[Dict[str, Any]]] = None,
    loans: Optional[List[Dict[str, Any]]] = None,
    override_raise_rate: Optional[float] = None,
    override_inflation_rate: Optional[float] = None
) -> Dict[str, Any]:
    """
    profile 格式:
    {
        "salary": 35000,
        "fixed_expense": 12000,
        "variable_expense": 6000,
        "balance": 50000,
        "raise_rate": 0.03,
        "inflation_rate": 0.02,
        "target_emergency_months": 3
    }
    """

    events = events or []
    loans = loans or []

    base_salary = profile["salary"]
    fixed_expense = profile["fixed_expense"]
    variable_expense = profile["variable_expense"]
    balance = float(profile["balance"])

    raise_rate = override_raise_rate if override_raise_rate is not None else profile.get("raise_rate", 0.03)
    inflation_rate = override_inflation_rate if override_inflation_rate is not None else profile.get("inflation_rate", 0.02)
    target_emergency_months = profile.get("target_emergency_months", 3)

    salary_events = [e for e in events if e.get("type") == "salary_change"]

    curve: List[Dict[str, Any]] = []

    for month in range(1, months + 1):
        base_income = monthly_income(base_salary, raise_rate, month)
        income = get_salary_for_month(month, base_income, salary_events)

        expense = monthly_expense(fixed_expense, variable_expense, inflation_rate, month)

        event_net = get_monthly_event_net(month, events)
        debt_payment = get_debt_payment_for_month(month, loans)

        net_cashflow = income - expense - debt_payment + event_net
        balance = balance + net_cashflow

        fsi = calculate_fsi(
            income=income,
            expense=expense,
            debt_payment=debt_payment,
            balance=balance,    
            target_emergency_months=target_emergency_months
        )
        risk_level = classify_risk(fsi, balance)

        curve.append({
            "month": month,
            "income": round(income, 2),
            "expense": round(expense, 2),
            "debt_payment": round(debt_payment, 2),
            "event_net": round(event_net, 2),
            "net_cashflow": round(net_cashflow, 2),
            "balance": round(balance, 2),
            "fsi": round(fsi, 4),
            "risk_level": risk_level
        })

    summary = summarize_simulation(curve)

    return {
        "simulation_curve": curve,
        "summary": summary
    }