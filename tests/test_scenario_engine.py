from copy import deepcopy
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.scenario_schemas import ScenarioComparisonRequest, ScenarioOption, ScenarioRequest
from app.services.calendar_period import YearMonth
from app.services.scenario_engine import build_scenario, compare_scenarios, find_baseline_option
from main import app


PROFILE = {"salary": 70000, "fixed_expense": 25000, "variable_expense": 15000, "balance": 500000,
           "raise_rate": 0, "inflation_rate": 0, "target_emergency_months": 3}


def sourced(value, source="user_provided"):
    return {"value": str(value), "source": source}


def vehicle(payment="financed", **overrides):
    payload = {"scenario_type": "vehicle_purchase", "purchase_price": sourced(600000),
               "payment_method": payment, "down_payment": sourced(200000),
               "loan_term_months": 60, "annual_interest_rate": sourced("0.03")}
    if payment == "cash":
        payload = {"scenario_type": "vehicle_purchase", "purchase_price": sourced(250000), "payment_method": "cash"}
    payload.update(overrides)
    return {"scenario_id": "vehicle-1", "scenario_type": "vehicle_purchase", "target_period": "2027-01",
            "horizon_months": 60, "payload": payload, "source_metadata": []}


def housing(**overrides):
    payload = {"scenario_type": "housing_change", "current_rent": sourced(9000), "new_rent": sourced(14000),
               "monthly_commute_change": sourced(-2500), "deposit": sourced(28000), "moving_cost": sourced(6000),
               "deposit_refundable": True}
    payload.update(overrides)
    return {"scenario_id": "housing-1", "scenario_type": "housing_change", "target_period": "2026-09",
            "horizon_months": 60, "payload": payload}


def comparison(scenario=None, options=None):
    baseline = {"option_id": "baseline", "label": "目前財務狀況", "is_baseline": True}
    options = options or ([baseline] if scenario is None else [baseline, {"option_id": "scenario", "label": "方案", "scenario_request": scenario}])
    return {"confirmed_profile": PROFILE, "start_period": "2026-07", "options": options, "seed": 7}


def test_typed_requests_use_decimal_yearmonth_and_reject_extra_invalid_horizon():
    req = ScenarioRequest.model_validate(vehicle())
    assert isinstance(req.target_period, YearMonth)
    assert req.payload.purchase_price.value == Decimal("600000")
    assert req.payload.purchase_price.source.value == "user_provided"
    with pytest.raises(Exception):
        ScenarioRequest.model_validate({**vehicle(), "horizon_months": 0})
    bad = vehicle(); bad["payload"]["unexpected"] = 1
    with pytest.raises(Exception):
        ScenarioRequest.model_validate(bad)


def test_discriminated_union_and_unsupported_type_fail():
    bad = vehicle(); bad["scenario_type"] = "housing_change"
    with pytest.raises(Exception): ScenarioRequest.model_validate(bad)
    bad = vehicle(); bad["scenario_type"] = "job_change"; bad["payload"]["scenario_type"] = "job_change"
    with pytest.raises(Exception): ScenarioRequest.model_validate(bad)


@pytest.mark.parametrize("position", [0, 1, 2])
def test_explicit_baseline_is_order_independent(position):
    baseline = ScenarioOption.model_validate({"option_id": "baseline", "label": "anything", "is_baseline": True})
    others = [ScenarioOption.model_validate({"option_id": f"s{i}", "label": "Baseline misleading", "scenario_request": vehicle()}) for i in range(2)]
    options = others[:]; options.insert(position, baseline)
    assert find_baseline_option(sorted(options, key=lambda item: item.label)).option_id == "baseline"


def test_missing_and_duplicate_baselines_fail():
    scenario = ScenarioOption.model_validate({"option_id": "x", "label": "Baseline", "scenario_request": vehicle()})
    with pytest.raises(ValueError, match="missing"): find_baseline_option([scenario])
    baseline = ScenarioOption.model_validate({"option_id": "baseline", "label": "x", "is_baseline": True})
    with pytest.raises(ValueError, match="multiple"): find_baseline_option([baseline, baseline])


def test_cash_vehicle_has_one_event_and_no_loan():
    build = build_scenario(ScenarioRequest.model_validate(vehicle("cash")), YearMonth(2026, 7))
    assert len(build.events) == 1 and build.events[0].amount == -250000
    assert build.events[0].month == 6
    assert build.loans == []
    assert not any(item.field == "total_interest" for item in build.derived_values)


def test_financed_vehicle_reuses_loan_and_prevents_double_counting():
    build = build_scenario(ScenarioRequest.model_validate(vehicle()), YearMonth(2026, 7))
    assert [event.name for event in build.events] == ["車輛頭期款"]
    assert build.loans[0].principal == 400000 and build.loans[0].months == 60
    facts = {item.field: item for item in build.derived_values}
    assert facts["loan_principal"].source.value == "derived"
    assert facts["monthly_loan_payment"].value > 0 and facts["total_interest"].value > 0


def test_explicit_loan_consistency_and_vehicle_validation():
    ok = vehicle(explicit_loan_amount=sourced(400000))
    assert build_scenario(ScenarioRequest.model_validate(ok), YearMonth(2026, 7)).loans[0].principal == 400000
    bad = vehicle(explicit_loan_amount=sourced(390000))
    with pytest.raises(ValueError, match="conflicts"): build_scenario(ScenarioRequest.model_validate(bad), YearMonth(2026, 7))
    bad = vehicle(down_payment=sourced(700000))
    with pytest.raises(ValueError, match="exceed"): build_scenario(ScenarioRequest.model_validate(bad), YearMonth(2026, 7))


def test_housing_keeps_events_separate_and_derives_net_effect():
    build = build_scenario(ScenarioRequest.model_validate(housing()), YearMonth(2026, 7))
    assert [item.name for item in build.events] == ["租金變動", "通勤費變動", "deposit", "moving_cost"]
    assert build.events[0].amount == -5000 and build.events[1].amount == 2500
    facts = {item.field: item.value for item in build.derived_values}
    assert facts["net_monthly_cash_flow_effect"] == Decimal("-2500.00")
    assert build.scenario_request.payload.broker_fee is None
    assert build.missing_fields == []


@pytest.mark.parametrize("rent,commute", [(5000, 1000), (-5000, 1000), (5000, -1000), (-5000, -1000)])
def test_housing_preserves_rent_and_commute_direction(rent, commute):
    raw = housing(current_rent=None, new_rent=None, monthly_rent_change=sourced(rent), monthly_commute_change=sourced(commute), broker_fee=sourced(0))
    build = build_scenario(ScenarioRequest.model_validate(raw), YearMonth(2026, 7))
    assert build.events[0].amount == -rent and build.events[1].amount == -commute


def test_comparison_is_deterministic_isolated_and_returns_real_periods():
    raw = comparison(vehicle())
    profile_before = deepcopy(raw["confirmed_profile"])
    req = ScenarioComparisonRequest.model_validate(raw)
    first = compare_scenarios(req); second = compare_scenarios(req)
    assert first == second and raw["confirmed_profile"] == profile_before
    delta = first.deltas[0]
    assert delta.baseline_option_id == "baseline" and delta.scenario_option_id == "scenario"
    assert isinstance(delta.minimum_balance_period, YearMonth)
    assert delta.total_new_debt == Decimal("400000.00") and delta.total_interest > 0
    assert len(first.baseline.simulation["simulation_curve"]) == len(first.scenarios[0].simulation["simulation_curve"]) == 60


def test_baseline_only_has_no_events_loans_or_delta():
    result = compare_scenarios(ScenarioComparisonRequest.model_validate(comparison()))
    assert result.baseline_only and result.scenarios == [] and result.deltas == []


def test_api_financed_cash_housing_baseline_and_errors():
    client = TestClient(app)
    for scenario in (vehicle(), vehicle("cash"), housing(broker_fee=sourced(0))):
        response = client.post("/scenarios/compare", json=comparison(scenario))
        assert response.status_code == 200, response.text
        assert response.json()["deltas"]
    assert client.post("/scenarios/compare", json=comparison()).json()["baseline_only"] is True
    no_baseline = comparison(options=[{"option_id": "x", "label": "Baseline", "scenario_request": vehicle()}])
    response = client.post("/scenarios/compare", json=no_baseline)
    assert response.status_code == 422 and "Traceback" not in response.text
