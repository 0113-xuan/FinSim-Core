from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.schemas import FinancialProfileDraft, ProfileValueSource
from app.services.profile_onboarding import (
    assistant_reply,
    confirm_draft,
    create_draft,
    extract_message,
    next_questions,
    update_draft,
)
from main import (
    CONFIRMED_DEMO_PROFILES,
    PROFILE_DRAFTS,
    PROFILES,
    app,
    get_onboarding_ai_provider,
)


client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_real_onboarding_provider():
    app.dependency_overrides[get_onboarding_ai_provider] = lambda: None
    yield
    app.dependency_overrides.pop(get_onboarding_ai_provider, None)


COMPLETE_MESSAGE = (
    "我有存款 120 萬，投資 30 萬，月薪 6 萬，"
    "每月固定支出 2 萬，生活費約 15000，想看未來 5 年，明年想買車。"
)


def complete_draft() -> FinancialProfileDraft:
    draft = extract_message(create_draft(), COMPLETE_MESSAGE)
    for field_name in (
        "cash_and_deposits",
        "monthly_salary",
        "fixed_expenses",
        "total_variable_expenses",
        "simulation_months",
    ):
        getattr(draft, field_name).confirmed = True
    for item in draft.variable_expense_allocation:
        item.confirmed = True
    return draft


def test_extracts_multiple_values_and_approximate_amounts():
    draft = extract_message(create_draft(), COMPLETE_MESSAGE)
    assert draft.cash_and_deposits.value == 1_200_000
    assert draft.investments.value == 300_000
    assert draft.monthly_salary.value == 60_000
    assert draft.fixed_expenses.value == 20_000
    assert draft.total_variable_expenses.value == 15_000
    assert draft.total_variable_expenses.confirmed is False
    assert draft.total_variable_expenses.source == "ai_extracted"
    assert draft.simulation_months.value == 60
    assert draft.future_plans[0].value.endswith("明年想買車。")


def test_asks_only_the_next_material_missing_question():
    questions = next_questions(create_draft())
    assert len(questions) == 1
    assert questions[0] == "現金與存款大約多少？"
    assert "突發支出" not in questions[0]


def test_questions_are_short_and_direct():
    draft = extract_message(create_draft(), "我有存款 80 萬")
    questions = next_questions(draft)
    assert len(questions) == 1
    assert questions[0] == "每月實領薪資大約多少？"
    reply = assistant_reply(draft)
    assert reply == questions[0]
    assert "謝謝" not in reply


def test_ambiguous_answer_asks_for_a_range_directly():
    draft = extract_message(create_draft(), "看情況，不太確定")
    questions = next_questions(draft)
    assert len(questions) == 1
    assert "大約金額或範圍" in questions[0]


def test_bare_numeric_answers_apply_to_the_current_question():
    draft = extract_message(create_draft(), "100000")
    assert draft.cash_and_deposits.value == 100_000
    assert next_questions(draft) == ["每月實領薪資大約多少？"]

    draft = extract_message(draft, "1000000")
    assert draft.monthly_salary.value == 1_000_000
    assert next_questions(draft) == ["每月固定支出大約多少？"]

    draft = extract_message(draft, "20000")
    assert draft.fixed_expenses.value == 20_000
    assert next_questions(draft) == ["每月生活支出大約多少？"]

    draft = extract_message(draft, "15000")
    assert draft.total_variable_expenses.value == 15_000
    assert next_questions(draft) == ["想模擬未來幾年？"]

    draft = extract_message(draft, "5")
    assert draft.simulation_months.value == 60
    assert next_questions(draft) == []


def test_bare_numeric_answer_recovers_from_a_spurious_conflict_loop():
    draft = extract_message(create_draft(), "100000")
    draft = extract_message(draft, "50000")
    draft = extract_message(draft, "6000")
    draft.conflicts = [
        "每月固定支出原為 6000.0，本次候選值為 2000.0，請確認要採用哪一個。"
    ]

    recovered = extract_message(draft, "3000")

    assert recovered.fixed_expenses.value == 6000
    assert recovered.total_variable_expenses.value == 3000
    assert recovered.conflicts == []
    assert next_questions(recovered) == ["想模擬未來幾年？"]


def test_explicit_duration_replaces_unconfirmed_default():
    draft = extract_message(create_draft(), "想模擬 3 年")
    assert draft.simulation_months.value == 36
    assert draft.conflicts == []


def test_normalizes_weekly_and_yearly_values_to_monthly():
    weekly = extract_message(create_draft(), "我的副業其他收入每週 3000 元")
    assert weekly.other_recurring_income.value == 13_000
    assert "每週金額換算為每月" in weekly.other_recurring_income.normalized_from

    yearly = extract_message(create_draft(), "我的年薪是 120 萬")
    assert yearly.monthly_salary.value == 100_000
    assert "每年金額換算為每月" in yearly.monthly_salary.normalized_from


def test_detects_contradictions_and_user_edit_resolves_them():
    draft = extract_message(create_draft(), "我的月薪是 6 萬")
    contradicted = extract_message(draft, "更正，我的月薪是 7 萬")
    assert contradicted.conflicts
    contradicted.monthly_salary.value = 70_000
    contradicted.monthly_salary.source = "user_modified"
    contradicted.monthly_salary.confirmed = True
    resolved = update_draft(contradicted, draft)
    assert resolved.conflicts == []


def test_estimated_allocation_matches_total_and_requires_confirmation():
    draft = extract_message(create_draft(), "每月生活費約 15000 元")
    assert len(draft.variable_expense_allocation) == 8
    assert sum(item.amount for item in draft.variable_expense_allocation) == 15_000
    assert round(sum(item.percentage for item in draft.variable_expense_allocation), 2) == 100
    assert all(item.source == "ai_estimated" and not item.confirmed for item in draft.variable_expense_allocation)


def test_confirmation_is_explicit_and_validated():
    draft = complete_draft()
    confirmed, profile = confirm_draft(draft)
    assert confirmed.status == "confirmed"
    assert confirmed.confirmed_at
    assert profile["balance"] == 1_500_000
    assert profile["variable_expense"] == 15_000

    draft.variable_expense_allocation[0].confirmed = False
    try:
        confirm_draft(draft)
        raise AssertionError("unconfirmed allocation should fail")
    except ValueError as exc:
        assert "變動支出分配" in str(exc)


def test_draft_api_persists_versions_and_does_not_overwrite_existing_profile():
    PROFILES["existing-user"] = {"salary": 999}
    response = client.post("/ai/financial-onboarding/message", json={"text": COMPLETE_MESSAGE})
    assert response.status_code == 200
    body = response.json()
    draft_id = body["draft"]["id"]
    assert draft_id in PROFILE_DRAFTS
    assert PROFILES["existing-user"] == {"salary": 999}
    read = client.get(f"/financial-profile-drafts/{draft_id}")
    assert read.status_code == 200
    assert read.json()["draft"]["version"] == body["draft"]["version"]


def test_api_rejects_confirmation_without_explicit_action():
    response = client.post("/ai/financial-onboarding/message", json={"text": COMPLETE_MESSAGE})
    draft = response.json()["draft"]
    result = client.post(
        f"/financial-profile-drafts/{draft['id']}/confirm",
        json={"draft": draft, "explicit_confirmation": False},
    )
    assert result.status_code == 400
    assert draft["id"] not in CONFIRMED_DEMO_PROFILES


def test_structured_output_schema_rejects_invalid_confidence():
    payload = complete_draft().model_dump()
    payload["monthly_salary"]["confidence"] = 1.5
    try:
        FinancialProfileDraft.model_validate(payload)
        raise AssertionError("invalid confidence should fail")
    except ValueError:
        pass


def test_provider_failure_uses_safe_fallback_without_losing_input():
    response = client.post(
        "/ai/financial-onboarding/message",
        json={"text": "我目前只有存款 50 萬"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider_available"] is False
    assert body["draft"]["cash_and_deposits"]["value"] == 500_000
    assert body["draft"]["audit_trail"][-1]["message_ref"]


def test_current_vehicle_debt_api_retains_11000_without_touching_fixed_expense():
    draft = create_draft()
    draft.fixed_expenses.value = 8_000
    draft.fixed_expenses.source = ProfileValueSource.user_provided
    draft.fixed_expenses.confirmed = True
    PROFILE_DRAFTS[draft.id] = draft

    response = client.post(
        "/ai/financial-onboarding/message",
        json={
            "draft_id": draft.id,
            "text": "我現在車貸還有60期，每個月繳11000元",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["draft"]["fixed_expenses"]["value"] == 8_000
    assert body["draft"]["monthly_debt_payments"]["value"] == 11_000
    assert body["draft"]["debts"][0]["monthly_payment"]["value"] == 11_000
    assert body["draft"]["debts"][0]["remaining_months"]["value"] == 60
    assert body["draft"]["future_plans"] == []
    assert body["draft"]["conflicts"] == []
    assert "2000" not in response.text


def test_weekly_income_api_exposes_backend_normalization_without_zero_conflict():
    response = client.post(
        "/ai/financial-onboarding/message",
        json={"text": "我每週打工賺5000元。"},
    )
    field = response.json()["draft"]["other_recurring_income"]

    assert response.status_code == 200
    assert field["value"] == 21_666.67
    assert field["original_amount"] == 5_000
    assert field["original_frequency"] == "weekly"
    assert field["normalization_source"] == "backend_calculation"
    assert field["source"] == "backend_normalized"
    assert response.json()["draft"]["conflicts"] == []


def test_review_waits_until_the_state_machine_has_no_next_question():
    response = client.post(
        "/ai/financial-onboarding/message",
        json={
            "text": (
                "我有存款 80 萬，月薪 6 萬，每月固定支出 2 萬，"
                "每月生活費 15000 元"
            )
        },
    )
    body = response.json()
    assert body["current_step"] == 5
    assert body["stage_label"] == "模擬期間"
    assert body["ready_for_review"] is False
    assert len(body["follow_up_questions"]) == 1


def test_one_time_plan_is_not_added_to_normal_expenses():
    draft = extract_message(create_draft(), "我明年想旅行，預算 8 萬")
    assert draft.future_plans
    assert draft.fixed_expenses.value is None
    assert draft.total_variable_expenses.value is None
