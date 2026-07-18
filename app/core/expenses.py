from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from app.schemas import ExpenseCategoryName, ExpenseMode


DEFAULT_CATEGORY_WEIGHTS = {
    ExpenseCategoryName.food.value: 0.28,
    ExpenseCategoryName.transportation.value: 0.16,
    ExpenseCategoryName.entertainment.value: 0.10,
    ExpenseCategoryName.shopping.value: 0.12,
    ExpenseCategoryName.medical.value: 0.06,
    ExpenseCategoryName.education.value: 0.06,
    ExpenseCategoryName.social.value: 0.07,
    ExpenseCategoryName.travel.value: 0.06,
    ExpenseCategoryName.family_support.value: 0.06,
    ExpenseCategoryName.other.value: 0.03,
}


def split_quick_variable_expense(total: float) -> List[Dict[str, Any]]:
    return [
        {
            "category": category,
            "baseline": round(float(total) * weight, 2),
            "monthly_volatility": 0.0,
            "annual_inflation_rate": 0.02,
            "income_elasticity": 0.0,
            "seasonal_factors": [1.0] * 12,
            "minimum": None,
            "maximum": None,
            "enabled": True,
        }
        for category, weight in DEFAULT_CATEGORY_WEIGHTS.items()
    ]


def _event_multiplier_for_category(month: int, category: str, events: List[Dict[str, Any]]) -> float:
    multiplier = 1.0
    for event in events:
        target = event.get("target_expense_category")
        if target and target != category:
            continue
        start = event.get("start_month") or event.get("month")
        end = event.get("end_month") or start
        if start and end and start <= month <= end:
            multiplier *= float(event.get("variable_expense_multiplier", 1.0) or 1.0)
    return multiplier


def _event_monthly_amount_for_category(month: int, category: str, events: List[Dict[str, Any]]) -> float:
    amount = 0.0
    for event in events:
        target = event.get("target_expense_category")
        if target and target != category:
            continue
        start = event.get("start_month") or event.get("month")
        end = event.get("end_month") or start
        if start and end and start <= month <= end:
            amount += float(event.get("category_monthly_adjustment", 0.0) or 0.0)
    return amount


def get_expense_categories(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    model = profile.get("variable_expense_model") or {}
    mode = model.get("mode", ExpenseMode.quick.value)
    categories = model.get("categories") or []
    if mode == ExpenseMode.advanced.value and categories:
        return [item for item in categories if item.get("enabled", True)]
    total = model.get("total_variable_expense", profile.get("variable_expense", 0))
    return split_quick_variable_expense(float(total or 0))


def calculate_variable_expenses(
    *,
    month: int,
    profile: Dict[str, Any],
    income: float,
    base_income: float,
    events: Optional[List[Dict[str, Any]]] = None,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    events = events or []
    rng = rng or random.Random(0)
    categories = get_expense_categories(profile)
    years_passed = (month - 1) // 12
    month_index = (month - 1) % 12
    total = 0.0
    details = []

    for category in categories:
        baseline = float(category.get("baseline", 0) or 0)
        seasonal_factor = float(category.get("seasonal_factors", [1.0] * 12)[month_index])
        inflation_factor = (1 + float(category.get("annual_inflation_rate", profile.get("inflation_rate", 0.02)))) ** years_passed
        income_ratio = income / base_income if base_income > 0 else 1.0
        elasticity_factor = income_ratio ** float(category.get("income_elasticity", 0.0) or 0.0)
        event_multiplier = _event_multiplier_for_category(month, category["category"], events)
        event_amount = _event_monthly_amount_for_category(month, category["category"], events)
        amount_before_event = baseline * seasonal_factor * inflation_factor * elasticity_factor
        amount = amount_before_event * event_multiplier + event_amount

        volatility = float(category.get("monthly_volatility", 0.0) or 0.0)
        if volatility > 0:
            amount *= max(0.0, rng.normalvariate(1.0, volatility))

        minimum = category.get("minimum")
        maximum = category.get("maximum")
        if minimum is not None:
            amount = max(amount, float(minimum))
        if maximum is not None:
            amount = min(amount, float(maximum))

        amount = round(max(0.0, amount), 2)
        total += amount
        details.append(
            {
                "category": category["category"],
                "amount": amount,
                "seasonal_factor": seasonal_factor,
                "inflation_factor": round(inflation_factor, 6),
                "income_elasticity_factor": round(elasticity_factor, 6),
                "event_multiplier": round(event_multiplier, 6),
                "event_amount": round(event_amount, 2),
                "amount_before_event": round(max(0.0, amount_before_event), 2),
            }
        )

    return {"total": round(total, 2), "categories": details}
