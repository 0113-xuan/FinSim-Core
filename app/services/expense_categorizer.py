from __future__ import annotations

from app.core.expenses import DEFAULT_CATEGORY_WEIGHTS
from app.schemas import CategorizeExpensesRequest, CategorizeExpensesResponse, CategorySuggestion


def categorize_expenses(req: CategorizeExpensesRequest) -> CategorizeExpensesResponse:
    total = float(req.total_variable_expense)
    suggestions = [
        CategorySuggestion(
            category=category,
            amount=round(total * weight, 2),
            confidence=0.6,
            reason="Default deterministic distribution; user can edit each category.",
        )
        for category, weight in DEFAULT_CATEGORY_WEIGHTS.items()
    ]
    diff = round(total - sum(item.amount for item in suggestions), 2)
    if suggestions:
        suggestions[-1].amount = round(suggestions[-1].amount + diff, 2)
    return CategorizeExpensesResponse(
        categories=suggestions,
        total=round(sum(item.amount for item in suggestions), 2),
        warnings=["AI unavailable or disabled; deterministic category split was used."],
    )
