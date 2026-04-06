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

    FSI = 0.5*(expense / income)
        + 0.3*(debt_payment / income)
        + 0.2*(緊急預備金不足程度)

    說明：
    - income <= 0 時，視為極高風險，直接回傳 999.0
    - 緊急預備金月數 = balance / expense
    - 若 expense <= 0，則視為已達成 target_emergency_months
    """
    if income <= 0:
        return 999.0

    if expense > 0:
        emergency_months = balance / expense
    else:
        emergency_months = target_emergency_months

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

    規則：
    - balance < 0 => crisis
    - fsi < 0.60 => low
    - fsi < 0.85 => medium
    - 其他 => high
    """
    if balance < 0:
        return "crisis"
    if fsi < 0.60:
        return "low"
    if fsi < 0.85:
        return "medium"
    return "high"
