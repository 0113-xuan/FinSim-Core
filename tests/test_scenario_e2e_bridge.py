from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from main import app


client = TestClient(app)
PROFILE = {"salary": 70000, "fixed_expense": 25000, "variable_expense": 15000,
           "balance": 500000, "raise_rate": 0, "inflation_rate": 0, "target_emergency_months": 3}


def parse(text):
    return client.post("/ai/parse-scenario", json={"text": text, "months": 60,
        "reference_date": "2026-07-21", "timezone": "Asia/Taipei"})


def compare(typed):
    return client.post("/scenarios/compare", json={"confirmed_profile": PROFILE,
        "start_period": "2026-07", "horizon_months": 60, "options": [
            {"option_id": "baseline", "label": "目前財務狀況", "is_baseline": True},
            {"option_id": typed["scenario_id"], "label": typed["scenario_id"],
             "is_baseline": False, "scenario_request": typed}]})


def test_financed_vehicle_natural_language_full_chain():
    parsed_response = parse("我明年3月想買一台60萬的車，頭期20萬，剩下貸60期，年利率3%。")
    assert parsed_response.status_code == 200
    parsed = parsed_response.json(); typed = parsed["typed_scenario_request"]
    assert parsed["events"] and parsed["display"] and typed["target_period"] == "2027-03"
    assert typed["payload"]["purchase_price"]["source"] == "user_provided"
    result = compare(typed); assert result.status_code == 200, result.text
    data = result.json(); build = data["scenarios"][0]["build"]
    assert len(data["scenarios"]) == 1 and len(build["loans"]) == 1
    assert build["loans"][0]["principal"] == 400000
    assert [event["name"] for event in build["events"]] == ["車輛頭期款"]
    facts = {item["field"]: item for item in build["derived_values"]}
    assert facts["loan_principal"]["source"] == "derived"
    assert facts["monthly_loan_payment"]["value"] == "7187.48"
    assert facts["total_interest"]["value"] == "31248.80"


def test_cash_vehicle_natural_language_full_chain():
    parsed = parse("我今年年底想用現金買一台25萬的二手車。").json()
    typed = parsed["typed_scenario_request"]
    assert typed["target_period"] == "2026-12" and typed["payload"]["payment_method"] == "cash"
    data = compare(typed).json(); build = data["scenarios"][0]["build"]
    assert len(build["events"]) == 1 and build["events"][0]["amount"] == -250000
    assert build["loans"] == [] and data["deltas"][0]["total_interest"] == "0.00"


def test_housing_natural_language_full_chain_preserves_separate_values():
    text = "我兩個月後搬家，目前房租9000，新房租14000，押金28000，搬家費6000，通勤每月可以少2500。"
    typed = parse(text).json()["typed_scenario_request"]
    assert typed["payload"]["broker_fee"] is None and typed["payload"]["deposit_refundable"] is None
    response = compare(typed); assert response.status_code == 200, response.text
    build = response.json()["scenarios"][0]["build"]
    assert [item["name"] for item in build["events"]] == ["租金變動", "通勤費變動", "deposit", "moving_cost"]
    assert not any(abs(item.get("amount") or 0) == 30000 for item in build["events"])


def test_incomplete_and_unsupported_remain_non_executable_and_compatible():
    incomplete = parse("我明年想買車。 ").json()
    assert incomplete["clarification"] and incomplete["typed_scenario_request"] is None
    unsupported = parse("我明年想換工作，薪水增加5000。 ").json()
    assert "events" in unsupported and "summary" in unsupported
    assert unsupported["typed_scenario_request"] is None


def test_original_text_profile_isolation_and_structured_baseline_error():
    text = "我今年年底想用現金買一台25萬的二手車。"
    typed = parse(text).json()["typed_scenario_request"]
    assert typed["original_text"] == text
    before = deepcopy(PROFILE); compare(typed); assert PROFILE == before
    bad = client.post("/scenarios/compare", json={"confirmed_profile": PROFILE, "start_period": "2026-07",
        "horizon_months": 60, "options": [{"option_id": "x", "label": "Baseline",
        "is_baseline": False, "scenario_request": typed}]})
    assert bad.status_code == 422 and "Traceback" not in bad.text
