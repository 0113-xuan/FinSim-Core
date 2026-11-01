"""Month-end asset and liability balances that complete net worth."""
from __future__ import annotations

from typing import Any, Dict, Iterable

from app.core.events import calculate_loan_payment


def asset_value(asset: Dict[str, Any], month: int) -> float:
    """Declining-balance value; the purchase month has been held for zero months."""
    start = int(asset["start_month"])
    if month < start:
        return 0.0
    return float(asset["value"]) * (1 - float(asset["annual_depreciation_rate"])) ** ((month - start) / 12)


def loan_balance(loan: Dict[str, Any], month: int, *, rounded: bool = True) -> float:
    """Principal left after this month's payment, using the same payment the cash flow deducts."""
    start, term = int(loan["start_month"]), int(loan["months"])
    if month < start:
        return 0.0
    paid = month - start + 1
    if paid >= term:
        # The final payment absorbs the cents left by a rounded monthly payment.
        return 0.0
    principal, apr = float(loan["principal"]), float(loan["apr"])
    payment = calculate_loan_payment(principal, apr, term, rounded=rounded)
    rate = apr / 12
    if rate == 0:
        return max(0.0, principal - payment * paid)
    growth = (1 + rate) ** paid
    return max(0.0, principal * growth - payment * (growth - 1) / rate)


def loan_interest_through(loan: Dict[str, Any], month: int) -> float:
    """Interest inside the payments made up to and including ``month``."""
    start, term = int(loan["start_month"]), int(loan["months"])
    paid = min(term, month - start + 1)
    if paid <= 0:
        return 0.0
    principal = float(loan["principal"])
    payment = calculate_loan_payment(principal, float(loan["apr"]), term)
    return payment * paid - (principal - loan_balance(loan, month))


def existing_debt_balance(debts: Iterable[Dict[str, Any]] | None, month: int) -> float:
    """Undiscounted payments still owed after this month, matching the dashboard."""
    return sum(float(debt["monthly_payment"]) * max(0, int(debt["remaining_months"]) - month)
               for debt in debts or [])
