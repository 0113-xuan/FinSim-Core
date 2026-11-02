from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Sequence

from app.core.events import (
    debt_to_income_for_month,
    get_debt_payment_for_month,
    get_fixed_expense_for_month,
    get_income_for_month,
    get_one_time_asset_impact,
    get_recurring_event_amount,
)
from app.core.balance_sheet import asset_value, existing_debt_balance, loan_balance
from app.core.expenses import calculate_variable_expenses
from app.core.market_data import load_market_history
from app.core.shocks import generate_shocks_for_month
from app.core.financial_rules import emergency_fund_months


class PriceLevel:
    """Annual-step price multipliers from a fixed annual rate or a monthly inflation path."""

    def __init__(self, months: int, annual_rate: float, monthly_path: Optional[Sequence[float]] = None):
        self.annual_rate = annual_rate
        self.cumulative = None
        if monthly_path is not None:
            if len(monthly_path) < months:
                raise ValueError("inflation path is shorter than the simulation")
            self.cumulative = [1.0]
            for rate in monthly_path[:months]:
                self.cumulative.append(self.cumulative[-1] * (1 + float(rate)))

    def year_multiplier(self, month: int) -> float:
        """Year k (months 12k+1..12k+12) uses the price change of the first 12k months."""
        years = (month - 1) // 12
        return self.cumulative[12 * years] if self.cumulative else (1 + self.annual_rate) ** years

    def growth(self, start_month: int, years: int) -> float:
        if not self.cumulative:
            return (1 + self.annual_rate) ** years
        return self.cumulative[start_month - 1 + 12 * years] / self.cumulative[start_month - 1]

    def total(self, months: int) -> float:
        return self.cumulative[months] if self.cumulative else (1 + self.annual_rate) ** (months / 12)


def summarize_simulation(simulation_curve: List[Dict[str, Any]], profile: Dict[str, Any]) -> Dict[str, Any]:
    if not simulation_curve:
        return {
            "final_balance": 0.0,
            "min_balance": 0.0,
            "minimum_cash_balance": 0.0,
            "minimum_cash_month": None,
            "first_negative_cash_month": None,
            "minimum_emergency_fund_months": None,
            "emergency_fund_coverage": 0.0,
            "debt_to_income": 0.0,
            "final_investment_value": 0.0,
            "final_asset_value": 0.0,
            "final_loan_balance": 0.0,
            "final_existing_debt_balance": 0.0,
            "final_net_worth": 0.0,
        }

    final_balance = simulation_curve[-1]["balance"]
    min_balance = min(item["balance"] for item in simulation_curve)
    final = simulation_curve[-1]
    coverage = emergency_fund_months(final_balance, final.get("living_expense", final["expense"]), final["debt_payment"])
    emergency_fund_coverage = coverage if coverage is not None else 0.0
    coverages = [r["emergency_fund_months"] for r in simulation_curve if r.get("emergency_fund_months") is not None]

    return {
        "final_balance": round(final_balance, 2),
        "min_balance": round(min_balance, 2),
        "minimum_cash_balance": round(min_balance, 2),
        "first_negative_cash_month": next((r["month"] for r in simulation_curve if r["balance"] < 0), None),
        "minimum_cash_month": min(simulation_curve, key=lambda r: r["balance"])["month"],
        "minimum_emergency_fund_months": round(min(coverages), 4) if coverages else None,
        "emergency_fund_coverage": round(emergency_fund_coverage, 2),
        "debt_to_income": simulation_curve[-1]["debt_to_income"],
        "target_emergency_months": profile.get("target_emergency_months", 3),
        "final_investment_value": round(final.get("investment_value", 0.0), 2),
        "final_asset_value": round(final.get("asset_value", 0.0), 2),
        "final_loan_balance": round(final.get("loan_balance", 0.0), 2),
        "final_existing_debt_balance": round(final.get("existing_debt_balance", 0.0), 2),
        "final_net_worth": round(final.get("net_worth", final_balance), 2),
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
    round_output: bool = True,
    inflation_path: Optional[Sequence[float]] = None,
    return_path: Optional[Sequence[float]] = None,
    assets: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Monthly cash, investment and net worth simulation.

    Net worth = cash + investments + depreciating ``assets`` − remaining loan
    principal − undiscounted payments left on ``existing_debts``.

    Without paths, inflation and investment returns are constant: the user's
    ``inflation_rate`` / ``expected_annual_return`` or the historical annual
    averages. Monte Carlo passes sampled monthly ``inflation_path`` and
    ``return_path`` instead.
    """
    if months <= 0:
        raise ValueError("months must be > 0")

    events = events or []
    # Cash-only ownership ranges can be numerous in long planner horizons.
    # Expense categories only inspect these two modifiers; keep cash transfers
    # in the full event list but avoid rescanning them for every category.
    expense_events = [event for event in events
                      if event.get('variable_expense_multiplier', 1) != 1
                      or event.get('category_monthly_adjustment', 0)]
    loans = loans or []
    assets = assets or []
    random_shocks = random_shocks or []
    rng = random.Random(seed)

    base_salary = float(profile["salary"])
    base_fixed_expense = float(profile["fixed_expense"])
    balance = float(profile["balance"])
    investment = float(profile.get("investment_value") or 0)
    investment_start = investment
    monthly_investment = float(profile.get("monthly_investment") or 0)
    requested_inflation = override_inflation_rate if override_inflation_rate is not None else profile.get("inflation_rate")
    if inflation_path is not None:
        requested_inflation = None
    inflation_rate = float(requested_inflation if requested_inflation is not None
                           else load_market_history().annual_inflation_rate)
    price_level = PriceLevel(months, inflation_rate, inflation_path)
    requested_raise_rate = override_raise_rate if override_raise_rate is not None else profile.get("raise_rate")
    raise_rate = float(inflation_rate if requested_raise_rate is None else requested_raise_rate)
    salary_growth = price_level.growth if requested_raise_rate is None and inflation_path is not None else None
    if return_path is not None:
        if len(return_path) < months:
            raise ValueError("return path is shorter than the simulation")
        monthly_returns = [float(rate) for rate in return_path[:months]]
    elif investment or monthly_investment:
        expected_return = profile.get("expected_annual_return")
        annual_return = float(expected_return if expected_return is not None
                              else load_market_history().annual_return_rate)
        monthly_returns = [(1 + annual_return) ** (1 / 12) - 1] * months
    else:
        monthly_returns = [0.0] * months

    profile = {**profile, "inflation_rate": inflation_rate}
    curve: List[Dict[str, Any]] = []
    shock_details: List[Dict[str, Any]] = []
    first_negative_cash_month = None

    for month in range(1, months + 1):
        years_passed = (month - 1) // 12
        price_multiplier = price_level.year_multiplier(month)
        scheduled_income = base_salary * (price_multiplier if requested_raise_rate is None
                                          else (1 + raise_rate) ** years_passed)
        income = get_income_for_month(month, scheduled_income, events, raise_rate=raise_rate,
                                      salary_growth=salary_growth)
        fixed_base = base_fixed_expense * (price_multiplier if profile.get("fixed_expense_inflates", False) else 1)
        fixed_expense = get_fixed_expense_for_month(month, fixed_base, events)
        variable_result = calculate_variable_expenses(
            month=month,
            profile=profile,
            income=income,
            base_income=max(base_salary, 1.0),
            events=expense_events,
            rng=rng,
            price_multiplier=price_multiplier,
        )
        existing_debts = profile.get("existing_debts")
        existing_payment = (sum(float(debt['monthly_payment']) for debt in existing_debts
                                if month <= debt['remaining_months'])
                            if existing_debts is not None else float(profile.get("required_monthly_debt", 0)))
        debt_payment = get_debt_payment_for_month(month, loans, rounded=round_output) + existing_payment
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
        # Contributions continue even when cash is negative; v1 never sells investments.
        investment = investment * (1 + monthly_returns[month - 1]) + monthly_investment
        net_cashflow = income - total_expense + recurring_event_amount + one_time_asset_impact - monthly_investment
        balance += net_cashflow
        if balance < 0 and first_negative_cash_month is None:
            first_negative_cash_month = month
        owned_assets = sum(asset_value(asset, month) for asset in assets)
        owed_loans = sum(loan_balance(loan, month, rounded=round_output) for loan in loans)
        owed_debts = existing_debt_balance(existing_debts, month)
        net_worth = balance + investment + owned_assets - owed_loans - owed_debts

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
            "investment_value": round(investment, 2),
            "asset_value": round(owned_assets, 2),
            "loan_balance": round(owed_loans, 2),
            "existing_debt_balance": round(owed_debts, 2),
            "net_worth": round(net_worth, 2),
            "debt_to_income": debt_to_income_for_month(month, income, loans),
        }
        if not round_output:
            # Constraint searches must evaluate calculated values before display rounding.
            row.update(income=income, fixed_expense=fixed_expense, debt_payment=debt_payment,
                       living_expense=living_expense, net_cashflow=net_cashflow, balance=balance,
                       investment_value=investment, asset_value=owned_assets, loan_balance=owed_loans,
                       existing_debt_balance=owed_debts, net_worth=net_worth)
        if include_details:
            row["expense_categories"] = variable_result["categories"]
        curve.append(row)

    result = {
        "simulation_curve": curve,
        "summary": summarize_simulation(curve, profile),
        "seed": seed,
        # The constant rates a deterministic run used, so the page can disclose them.
        "assumptions": {
            "annual_inflation_rate": None if inflation_path is not None else round(inflation_rate, 6),
            "inflation_source": ("sampled" if inflation_path is not None
                                 else "user" if requested_inflation is not None else "historical_average"),
            "raise_rate": None if requested_raise_rate is None else round(raise_rate, 6),
            "raise_source": "user" if requested_raise_rate is not None else "follows_inflation",
            "annual_return_rate": (round(annual_return, 6)
                                   if return_path is None and (investment_start or monthly_investment) else None),
            "return_source": ("sampled" if return_path is not None
                              else "user" if profile.get("expected_annual_return") is not None
                              else "historical_average"),
        },
    }
    # The zero boundary is evaluated before currency display rounding.
    result["summary"]["first_negative_cash_month"] = first_negative_cash_month
    # Dividing a nominal amount by this gives today's purchasing power.
    result["summary"]["cumulative_price_multiplier"] = round(price_level.total(months), 6)
    if include_details:
        result["shock_details"] = shock_details
    return result
