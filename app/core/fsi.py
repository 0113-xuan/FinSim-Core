from typing import Literal
from app.core.financial_rules import emergency_fund_months


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
    - 緊急預備金月數 = balance / (expense + debt_payment)
    - 無必要支出時，共用函式回傳 None，舊版 FSI 視為無預備金缺口
    """
    if income <= 0:
        return 999.0

    coverage = emergency_fund_months(balance, expense, debt_payment)
    emergency_months = target_emergency_months if coverage is None else coverage

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
    - fsi < 0.30 => low
    - fsi < 0.60 => medium
    - fsi < 0.90 => high
    - 其他 => crisis
    """
    if balance < 0:
        return "crisis"
    if fsi < 0.30:
        return "low"
    if fsi < 0.60:
        return "medium"
    if fsi < 0.90:
        return "high"
    return "crisis"
