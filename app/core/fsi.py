# fsi.py
from typing import Literal


def calculate_fsi(
    income: float,
    expense: float,
    debt_payment: float,
    balance: float,
    target_emergency_months: float = 3.0
) -> float:
    """
    計算財務壓力指數 FSI

    FSI = 0.5*(expense/income)
        + 0.3*(debt/income)
        + 0.2*(預備金不足程度)

    若 income <= 0，直接視為高風險。
    """
    if income <= 0:
        return 999.0

    emergency_months = balance / expense if expense > 0 else target_emergency_months
    emergency_gap = max(0.0, 1.0 - (emergency_months / target_emergency_months))

    fsi = (
        0.5 * (expense / income)
        + 0.3 * (debt_payment / income)
        + 0.2 * emergency_gap
    )
    return round(fsi, 4)


def classify_risk(fsi: float, balance: float) -> Literal["low", "medium", "high", "crisis"]:
    """
    依據 FSI 與 balance 判斷風險等級
    """
    if balance < 0:
        return "crisis"
    if fsi < 0.60:
        return "low"
    if fsi < 0.85:
        return "medium"
    return "high"