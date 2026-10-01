"""Shared cash coverage and annual-step inflation rules."""


def emergency_fund_months(cash: float, living: float, debt: float) -> float | None:
    required = max(0.0, living + debt)
    return cash / required if required > 0 else None


def emergency_shortfall(cash: float, living: float, debt: float, target: float) -> float:
    return max(0.0, target * max(0.0, living + debt) - cash)


def inflation_factor(month: int, rate: float) -> float:
    return (1 + rate) ** ((month - 1) // 12)


def value_or_default(value, default):
    return default if value is None else value
