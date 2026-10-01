from __future__ import annotations

from typing import Any, Dict, List
from app.core.financial_rules import value_or_default


def calculate_loan_payment(principal: float, apr: float, months: int) -> float:
    if months <= 0:
        raise ValueError("months must be > 0")
    if principal < 0:
        raise ValueError("principal must be >= 0")
    if apr <= 0:
        return round(principal / months, 2)
    monthly_rate = apr / 12
    payment = principal * monthly_rate / (1 - (1 + monthly_rate) ** (-months))
    return round(payment, 2)


def is_event_active(event: Dict[str, Any], month: int) -> bool:
    event_type = event.get("type", "life_event")
    if event_type == "one_time":
        return event.get("month") == month
    start = event.get("start_month") or event.get("month")
    end = event.get("end_month") or start
    return bool(start and end and start <= month <= end)


def get_one_time_asset_impact(month: int, events: List[Dict[str, Any]]) -> float:
    total = 0.0
    for event in events:
        if event.get("type") == "one_time" and event.get("month") == month:
            total += float(event.get("amount", 0) or 0)
        elif is_event_active(event, month):
            start = event.get("start_month") or event.get("month")
            if start == month:
                total += float(event.get("one_time_amount", 0) or 0)
    return round(total, 2)


def get_recurring_event_amount(month: int, events: List[Dict[str, Any]]) -> float:
    total = 0.0
    for event in events:
        if is_event_active(event, month):
            if event.get("type") == "range":
                total += float(event.get("amount", 0) or 0)
            total += float(event.get("monthly_amount", 0) or 0)
    return round(total, 2)


def get_income_for_month(month: int, base_income: float, events: List[Dict[str, Any]]) -> float:
    salary = float(base_income)
    for event in sorted(events, key=lambda item: item.get("start_month") or item.get("month") or 0):
        if event.get("type") == "salary_change" and event.get("start_month", 999999) <= month:
            salary = float(value_or_default(event.get("new_salary"), salary))
        elif is_event_active(event, month):
            salary *= float(value_or_default(event.get("income_multiplier"), 1.0))
    return round(max(0.0, salary), 2)


def get_fixed_expense_for_month(month: int, base_fixed_expense: float, events: List[Dict[str, Any]]) -> float:
    fixed = float(base_fixed_expense)
    for event in events:
        if is_event_active(event, month):
            fixed *= float(value_or_default(event.get("fixed_expense_multiplier"), 1.0))
    return round(max(0.0, fixed), 2)


def get_debt_payment_for_month(month: int, loans: List[Dict[str, Any]]) -> float:
    total = 0.0
    for loan in loans:
        start_month = int(loan["start_month"])
        loan_months = int(loan["months"])
        end_month = start_month + loan_months - 1
        if start_month <= month <= end_month:
            total += calculate_loan_payment(float(loan["principal"]), float(loan["apr"]), loan_months)
    return round(total, 2)


def debt_to_income_for_month(month: int, income: float, loans: List[Dict[str, Any]]) -> float:
    if income <= 0:
        return 999.0
    return round(get_debt_payment_for_month(month, loans) / income, 4)
