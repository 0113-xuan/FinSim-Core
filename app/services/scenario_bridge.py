from __future__ import annotations

from decimal import Decimal

from app.core.transparency import display_source_label
from app.scenario_schemas import ScenarioRequest, ValueSource


def _sourced(value: Decimal | None, source: ValueSource = ValueSource.user_provided) -> dict | None:
    return None if value is None else {"value": value, "source": source.value}


def build_vehicle_scenario_request(*, scenario_id: str, target_period: str, horizon_months: int,
    original_text: str, purchase_price: Decimal, payment_method: str,
    down_payment: Decimal | None = None, explicit_loan_amount: Decimal | None = None,
    loan_term_months: int | None = None, annual_interest_rate_percent: Decimal | None = None,
    vehicle_condition: str | None = None,
    annual_maintenance_budget: Decimal | None = None,
    annual_maintenance_source: ValueSource = ValueSource.system_assumption,
) -> ScenarioRequest:
    assumptions = []
    if annual_maintenance_budget is not None and annual_maintenance_source == ValueSource.system_assumption:
        assumptions.append({
            "field": "annual_maintenance_budget",
            "value": annual_maintenance_budget,
            "source": annual_maintenance_source.value,
            "display_source": display_source_label(annual_maintenance_source),
            "reason": "車輛年度維護規劃預算",
        })
    return ScenarioRequest.model_validate({
        "scenario_id": scenario_id, "scenario_type": "vehicle_purchase", "target_period": target_period,
        "horizon_months": horizon_months, "original_text": original_text, "source_metadata": [],
        "assumptions": assumptions,
        "payload": {"scenario_type": "vehicle_purchase", "purchase_price": _sourced(purchase_price),
            "payment_method": payment_method, "down_payment": _sourced(down_payment),
            "explicit_loan_amount": _sourced(explicit_loan_amount), "loan_term_months": loan_term_months,
            "annual_interest_rate": _sourced(annual_interest_rate_percent / Decimal(100)) if annual_interest_rate_percent is not None else None,
            "vehicle_condition": vehicle_condition,
            "annual_maintenance_budget": _sourced(annual_maintenance_budget, annual_maintenance_source)},
    })


def build_housing_scenario_request(*, scenario_id: str, target_period: str, horizon_months: int,
    original_text: str, current_rent: Decimal | None, new_rent: Decimal | None,
    monthly_rent_change: Decimal | None, monthly_commute_change: Decimal,
    deposit: Decimal | None, moving_cost: Decimal | None) -> ScenarioRequest:
    return ScenarioRequest.model_validate({
        "scenario_id": scenario_id, "scenario_type": "housing_change", "target_period": target_period,
        "horizon_months": horizon_months, "original_text": original_text,
        "payload": {"scenario_type": "housing_change", "current_rent": _sourced(current_rent),
            "new_rent": _sourced(new_rent), "monthly_rent_change": _sourced(monthly_rent_change),
            "monthly_commute_change": _sourced(monthly_commute_change), "deposit": _sourced(deposit),
            "moving_cost": _sourced(moving_cost), "broker_fee": None, "deposit_refundable": None},
    })
