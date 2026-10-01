import pytest
from fastapi.testclient import TestClient

from main import app
from app.scenario_schemas import ScenarioDraftMessageRequest
from app.services.scenario_draft import continue_scenario_draft


client = TestClient(app)
BASE = {
    "months": 60,
    "reference_date": "2026-07-21",
    "timezone": "Asia/Taipei",
}


def send(message: str, draft=None):
    payload = {**BASE, "message": message}
    if draft is not None:
        payload["draft"] = draft
    return client.post("/scenarios/draft/message", json=payload)


def test_vehicle_draft_asks_one_question_then_builds_typed_request():
    first = send("我明年3月想買一台60萬的車。")
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["ready_for_review"] is False
    assert first_body["draft"]["status"] == "collecting"
    assert first_body["draft"]["scenario_type"] == "vehicle_purchase"
    assert first_body["draft"]["next_question"] == "會用現金一次付清，還是辦理貸款？"
    assert len(first_body["parsed"]["clarification"]["questions"]) == 1

    second = send("貸款，頭期20萬，貸60期，年利率3%。", first_body["draft"])
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["ready_for_review"] is True
    assert body["draft"]["status"] == "ready_for_review"
    typed = body["draft"]["scenario_request"]
    assert typed["target_period"] == "2027-03"
    assert typed["payload"]["purchase_price"]["value"] == "600000.0"
    assert typed["payload"]["down_payment"]["value"] == "200000.0"
    assert typed["payload"]["loan_term_months"] == 60
    assert typed["payload"]["annual_interest_rate"]["value"] == "0.03"
    assert typed["payload"]["annual_maintenance_budget"]["value"] == "18000"
    assert typed["payload"]["annual_maintenance_budget"]["source"] == "system_assumption"
    assert body["draft"]["missing_fields"] == []
    assert body["draft"]["next_question"] is None


def test_housing_draft_combines_follow_up_without_inventing_costs():
    first = send("我想搬家。").json()
    assert first["draft"]["next_question"] == "預計什麼時候搬家？"
    second = send(
        "兩個月後，目前房租9000，新房租14000，押金28000，搬家費6000，通勤每月少2500。",
        first["draft"],
    )
    assert second.status_code == 200, second.text
    typed = second.json()["draft"]["scenario_request"]
    assert typed["scenario_type"] == "housing_change"
    assert typed["target_period"] == "2026-09"
    assert typed["payload"]["deposit"]["value"] == "28000.00"
    assert typed["payload"]["moving_cost"]["value"] == "6000.00"
    assert typed["payload"]["broker_fee"] is None


def test_housing_draft_accepts_half_year_short_answer_and_explicit_unknowns():
    first = send("搬家，每月房租增加8000元。").json()
    assert first["draft"]["next_question"] == "預計什麼時候搬家？"
    second = send("半年後", first["draft"])
    assert second.status_code == 200, second.text
    assert second.json()["draft"]["next_question"].startswith("是否有押金")
    third = send("押金和搬家費不知道，通勤費不變", second.json()["draft"])
    assert third.status_code == 200, third.text
    body = third.json()
    assert body["ready_for_review"] is True
    assert body["draft"]["scenario_request"]["target_period"] == "2027-01"
    assert body["draft"]["scenario_request"]["payload"]["monthly_commute_change"]["value"] == "0"
    assert "一次性搬家費用保留為未知" in body["parsed"]["warnings"][0]


def test_housing_draft_understands_contextual_bare_answers():
    first = send("搬家，每月房租增加8000元。").json()
    second = send("半年後", first["draft"]).json()
    assert second["draft"]["next_question"].startswith("是否有押金")

    third = send("不知道", second["draft"])
    assert third.status_code == 200, third.text
    third_body = third.json()
    assert third_body["draft"]["next_question"].startswith("搬家後每月通勤費")

    fourth = send("不變", third_body["draft"])
    assert fourth.status_code == 200, fourth.text
    body = fourth.json()
    assert body["ready_for_review"] is True
    assert body["draft"]["scenario_request"]["target_period"] == "2027-01"
    assert body["draft"]["scenario_request"]["payload"]["monthly_commute_change"]["value"] == "0"
    assert body["draft"]["messages"][-2:] == [
        "押金、仲介費和搬家費都不知道",
        "通勤費不變",
    ]


@pytest.mark.parametrize("current,new", [("60000", "50000"), ("0", "12000")])
def test_housing_rent_answers_advance_without_repeating(current, new):
    first = send("半年後搬家").json()
    assert first["draft"]["next_question"] == "目前房租是多少？"
    second = send(current, first["draft"]).json()
    assert "current_rent" not in second["draft"]["missing_fields"]
    assert second["draft"]["next_question"] == "新房租大約多少？"
    third = send(new, second["draft"]).json()
    assert third["draft"]["next_question"].startswith("是否有押金")
    fourth = send("沒有", third["draft"]).json()
    final = send("不變", fourth["draft"]).json()
    assert final["ready_for_review"] is True
    payload = final["draft"]["scenario_request"]["payload"]
    assert float(payload["current_rent"]["value"]) == float(current)
    assert float(payload["new_rent"]["value"]) == float(new)


def test_housing_known_new_rent_only_asks_for_current_rent():
    first = send("半年後搬家，新房租50000").json()
    assert "new_rent" not in first["draft"]["missing_fields"]
    second = send("60000", first["draft"]).json()
    assert second["draft"]["next_question"].startswith("是否有押金")


def test_draft_is_client_held_and_not_implicitly_reused():
    first = send("我明年3月想買一台60萬的車。").json()
    assert first["draft"]["messages"] == ["我明年3月想買一台60萬的車。"]
    without_draft = send("貸款，頭期20萬，貸60期，年利率3%。")
    assert without_draft.status_code == 200
    assert without_draft.json()["ready_for_review"] is False
    assert without_draft.json()["draft"]["draft_id"] != first["draft"]["draft_id"]


def test_conflicting_scenario_type_requires_restart():
    first = send("我明年3月想買一台60萬的車。").json()
    response = send(
        "改成兩個月後搬家，目前房租9000，新房租14000，搬家費6000，通勤每月少2500。",
        first["draft"],
    )
    assert response.status_code == 422
    assert "情境類型衝突" in response.json()["detail"]
    assert "Traceback" not in response.text


def test_draft_rejects_unexpected_properties():
    response = client.post(
        "/scenarios/draft/message",
        json={**BASE, "message": "我想買車", "unexpected": True},
    )
    assert response.status_code == 422


def test_confirmation_requires_explicit_action_and_complete_draft():
    collecting = send("我明年3月想買一台60萬的車。").json()["draft"]
    incomplete = client.post(
        "/scenarios/draft/confirm",
        json={"draft": collecting, "explicit_confirmation": True},
    )
    assert incomplete.status_code == 422

    ready = send(
        "貸款，頭期20萬，貸60期，年利率3%。",
        collecting,
    ).json()["draft"]
    implicit = client.post(
        "/scenarios/draft/confirm",
        json={"draft": ready, "explicit_confirmation": False},
    )
    assert implicit.status_code == 400
    assert "明確確認" in implicit.json()["detail"]

    confirmed = client.post(
        "/scenarios/draft/confirm",
        json={"draft": ready, "explicit_confirmation": True},
    )
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["draft"]["status"] == "confirmed"
    assert body["scenario_request"] == ready["scenario_request"]
    repeated = client.post(
        "/scenarios/draft/confirm",
        json={"draft": body["draft"], "explicit_confirmation": True},
    )
    assert repeated.status_code == 200


def test_confirmation_does_not_persist_or_mutate_input_draft():
    ready = send("我今年年底想用現金買一台25萬的二手車。").json()["draft"]
    original = ready.copy()
    response = client.post(
        "/scenarios/draft/confirm",
        json={"draft": ready, "explicit_confirmation": True},
    )
    assert response.status_code == 200
    assert ready == original


@pytest.mark.parametrize("status", ["ready_for_review", "confirmed"])
def test_completed_draft_cannot_receive_more_messages(status):
    ready = send("我今年年底想用現金買一台25萬的二手車。").json()["draft"]
    ready["status"] = status
    request = ScenarioDraftMessageRequest.model_validate({**BASE, "message": "再補一個資訊", "draft": ready})
    with pytest.raises(ValueError, match="已完成"):
        continue_scenario_draft(request)
