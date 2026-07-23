from __future__ import annotations

from decimal import Decimal

from app.scenario_schemas import ScenarioRequest


def _sourced(value: Decimal | None) -> dict | None:
    return None if value is None else {"value": value, "source": "user_provided"}


def build_vehicle_scenario_request(*, scenario_id: str, target_period: str, horizon_months: int,
    original_text: str, purchase_price: Decimal, payment_method: str,
    down_payment: Decimal | None = None, explicit_loan_amount: Decimal | None = None,
    loan_term_months: int | None = None, annual_interest_rate_percent: Decimal | None = None,
    vehicle_condition: str | None = None) -> ScenarioRequest:
    return ScenarioRequest.model_validate({
        "scenario_id": scenario_id, "scenario_type": "vehicle_purchase", "target_period": target_period,
        "horizon_months": horizon_months, "original_text": original_text, "source_metadata": [],
        "payload": {"scenario_type": "vehicle_purchase", "purchase_price": _sourced(purchase_price),
            "payment_method": payment_method, "down_payment": _sourced(down_payment),
            "explicit_loan_amount": _sourced(explicit_loan_amount), "loan_term_months": loan_term_months,
            "annual_interest_rate": _sourced(annual_interest_rate_percent / Decimal(100)) if annual_interest_rate_percent is not None else None,
            "vehicle_condition": vehicle_condition},
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
