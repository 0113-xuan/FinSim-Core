import asyncio
import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.extraction_schemas import FinancialExtractionResult
import app.services.ai_provider as ai_provider_module
from app.services.ai_provider import AIProviderError, OpenAIProvider, parse_structured_content
from app.services.financial_answer_extraction import (
    ExtractionNormalizationError,
    deterministic_current_debt_extraction,
    extract_financial_answer,
    merge_deterministic_debt_candidates,
    validate_normalizations,
)
from app.services.mock_ai_provider import MockAIProvider
from app.services.profile_onboarding import create_draft, merge_extraction_candidates
from app.services.prompt_loader import load_prompt
from main import app, get_onboarding_ai_provider


def empty_result(**overrides):
    payload = {
        "fields": [],
        "variable_expense_allocation": [],
        "debts": [],
        "future_plans": [],
        "future_plan_conflicts": [],
        "ambiguities": [],
        "conflicts": [],
    }
    payload.update(overrides)
    return payload


def field_candidate(
    field,
    value,
    *,
    original_value,
    currency="TWD",
    source="user_provided",
    confidence=0.98,
    value_range=None,
    original_amount=None,
    original_frequency=None,
    normalized_frequency=None,
    normalized_from=None,
):
    return {
        "field": field,
        "value": value,
        "value_range": value_range,
        "currency": None if field in ("simulation_months", "risk_preference") else currency,
        "source": source,
        "confidence": confidence,
        "confirmed": False,
        "reason": "依使用者目前訊息直接擷取",
        "original_value": original_value,
        "original_amount": original_amount,
        "original_frequency": original_frequency,
        "normalized_frequency": normalized_frequency,
        "normalized_from": normalized_from,
    }


@pytest.mark.parametrize(
    ("message", "debt_type", "balance"),
    [
        ("我有學貸15萬", "student_loan", 150_000),
        ("信用卡債五萬", "credit_card", 50_000),
        ("目前信貸還有30萬", "personal_loan", 300_000),
    ],
)
def test_deterministic_current_debt_balance_does_not_invent_monthly_payment(
    message, debt_type, balance
):
    result = deterministic_current_debt_extraction(message)
    assert result is not None
    assert result.debts[0].debt_type.value == debt_type
    assert result.debts[0].remaining_balance == balance
    assert result.debts[0].monthly_payment is None
    assert result.debts[0].currency.value == "TWD"


def test_deterministic_current_debt_extracts_payment_term_and_rate():
    result = deterministic_current_debt_extraction(
        "房貸還有500萬，每月繳25000元，剩餘240期，年利率2%"
    )
    assert result is not None
    debt = result.debts[0]
    assert debt.remaining_balance == 5_000_000
    assert debt.monthly_payment == 25_000
    assert debt.remaining_months == 240
    assert debt.annual_interest_rate == 0.02


def test_future_vehicle_loan_is_not_misclassified_as_current_debt():
    assert deterministic_current_debt_extraction("我明年想買車，預計辦車貸50萬") is None


def test_deterministic_debt_overlay_preserves_provider_fields():
    provider_result = FinancialExtractionResult.model_validate(empty_result(fields=[
        field_candidate(
            "monthly_salary",
            60_000,
            original_value="月薪6萬",
        )
    ]))
    debts = deterministic_current_debt_extraction("月薪6萬，有學貸15萬")
    combined = merge_deterministic_debt_candidates(provider_result, debts)
    assert combined.fields[0].value == 60_000
    assert combined.debts[0].remaining_balance == 150_000


def run_mock(payload, answer="fixture answer"):
    provider = MockAIProvider({answer: payload})
    return asyncio.run(
        extract_financial_answer(
            provider=provider,
            answer=answer,
            current_values={},
            current_question="目前每月收入大約多少？",
        )
    )


def test_fixed_prompt_is_loaded_from_backend_prompt_file():
    prompt = load_prompt("financial_answer_extraction.md")
    assert "Return extraction candidates only" in prompt
    assert "52 / 12" in prompt
    assert "Never update, confirm, merge, or persist" in prompt


def test_explicit_amounts_chinese_units_english_k_and_multiple_fields():
    payload = empty_result(fields=[
        field_candidate("cash_and_deposits", 800_000, original_value="存款 80 萬", original_amount=800_000),
        field_candidate("monthly_salary", 50_000, original_value="月薪 50k", original_amount=50_000),
        field_candidate("fixed_expenses", 12_000, original_value="房租 12 千", original_amount=12_000),
    ])
    result = run_mock(payload, "存款 80 萬、月薪 50k、房租 12 千")
    assert [item.value for item in result.fields] == [800_000, 50_000, 12_000]
    assert all(item.currency.value == "TWD" for item in result.fields)


def test_approximate_range_uses_midpoint_and_twd_currency():
    value_range = {
        "minimum": 45_000,
        "maximum": 50_000,
        "midpoint": 47_500,
        "currency": "TWD",
    }
    payload = empty_result(fields=[
        field_candidate(
            "monthly_salary",
            47_500,
            original_value="大約 45k 到 50k",
            currency="TWD",
            source="ai_extracted",
            confidence=0.82,
            value_range=value_range,
        )
    ])
    item = run_mock(payload, "大約 45k 到 50k").fields[0]
    assert item.value_range.midpoint == 47_500
    assert item.currency.value == "TWD"
    assert item.confidence == 0.82


@pytest.mark.parametrize(
    ("field", "original", "frequency", "expected"),
    [
        ("other_recurring_income", 3_000, "weekly", 13_000),
        ("monthly_salary", 1_200_000, "yearly", 100_000),
        ("other_recurring_income", 6_000, "biweekly", 13_000),
        ("other_recurring_income", 30_000, "quarterly", 10_000),
    ],
)
def test_backend_verifies_allowed_monthly_normalization(field, original, frequency, expected):
    payload = empty_result(fields=[
        field_candidate(
            field,
            expected,
            original_value=f"{original} {frequency}",
            source="ai_extracted",
            confidence=0.88,
            original_amount=original,
            original_frequency=frequency,
            normalized_frequency="monthly",
            normalized_from=f"{frequency} to monthly",
        )
    ])
    assert run_mock(payload).fields[0].value == expected


def test_backend_rejects_incorrect_model_normalization():
    payload = empty_result(fields=[
        field_candidate(
            "other_recurring_income",
            12_000,
            original_value="每週 3000",
            source="ai_extracted",
            original_amount=3_000,
            original_frequency="weekly",
            normalized_frequency="monthly",
            normalized_from="weekly to monthly",
        )
    ])
    with pytest.raises(ExtractionNormalizationError):
        validate_normalizations(FinancialExtractionResult.model_validate(payload))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["fields"][0].update({"unknown_property": True}),
        lambda p: p["fields"][0].update({"field": "unsupported_field"}),
        lambda p: p["fields"][0].update({"source": "made_up"}),
        lambda p: p["fields"][0].update({"confidence": 1.1}),
        lambda p: p["fields"][0].update({"value": -1}),
    ],
)
def test_strict_schema_rejects_unknown_or_invalid_values(mutation):
    payload = empty_result(fields=[
        field_candidate("monthly_salary", 50_000, original_value="月薪五萬")
    ])
    mutation(payload)
    with pytest.raises(ValidationError):
        FinancialExtractionResult.model_validate(payload)


def test_schema_rejects_malformed_range_and_non_json_response():
    payload = empty_result(fields=[
        field_candidate(
            "monthly_salary",
            40_000,
            original_value="四到五萬",
            value_range={
                "minimum": 50_000,
                "maximum": 40_000,
                "midpoint": 45_000,
                "currency": "TWD",
            },
        )
    ])
    with pytest.raises(ValidationError):
        FinancialExtractionResult.model_validate(payload)
    with pytest.raises(AIProviderError):
        parse_structured_content("not JSON", FinancialExtractionResult)


def test_no_debt_no_investments_vague_answer_and_conflict_candidates():
    payload = empty_result(
        fields=[field_candidate("investments", 0, original_value="沒有投資", original_amount=0)],
        debts=[{
            "debt_type": "none",
            "name": None,
            "remaining_balance": 0,
            "monthly_payment": 0,
            "annual_interest_rate": None,
            "remaining_months": None,
            "currency": "TWD",
            "source": "user_provided",
            "confidence": 0.99,
            "reason": "使用者明確表示沒有負債",
            "original_value": "沒有貸款",
        }],
        ambiguities=[{
            "field": "total_variable_expenses",
            "message": "生活費只回答看情況，沒有可擷取金額",
            "clarification_question": "可以提供每月生活費的大約範圍嗎？",
        }],
        conflicts=[{
            "field": "monthly_salary",
            "existing_value": 50_000,
            "candidate_value": 60_000,
            "reason": "目前訊息與既有候選值不同",
        }],
    )
    result = run_mock(payload, "我沒貸款也沒投資，生活費看情況，月薪六萬")
    assert result.debts[0].debt_type.value == "none"
    assert result.fields[0].value == 0
    assert result.ambiguities and result.conflicts


def test_future_plan_without_cost_stays_null_and_one_time_is_not_recurring():
    payload = empty_result(future_plans=[{
        "plan_type": "travel",
        "title": "日本旅行",
        "description": "明年去日本旅行",
        "original_target_date_text": "明年",
        "normalized_target_date": None,
        "estimated_cost": None,
        "down_payment": None,
        "financing": None,
        "recurring_monthly_amount": None,
        "currency": "TWD",
        "source": "ai_extracted",
        "confirmed": False,
        "confidence": 0.93,
        "reason": "使用者提到未來旅行但未提供預算",
        "source_text": "明年想去日本旅行",
    }])
    plan = run_mock(payload, "明年想去日本旅行").future_plans[0]
    assert plan.estimated_cost is None
    assert plan.recurring_monthly_amount is None

    one_time = dict(payload["future_plans"][0])
    one_time.update({"estimated_cost": 80_000, "currency": "TWD"})
    draft = merge_extraction_candidates(
        create_draft(),
        FinancialExtractionResult.model_validate(empty_result(future_plans=[one_time])),
        "明年旅行一次，預算八萬",
    )
    assert draft.future_plans
    assert draft.fixed_expenses.value is None
    assert draft.total_variable_expenses.value is None

    invalid_recurring = empty_result(fields=[
        field_candidate(
            "fixed_expenses",
            80_000,
            original_value="旅行一次八萬元",
            original_amount=80_000,
            original_frequency="one_time",
        )
    ])
    with pytest.raises(ValidationError):
        FinancialExtractionResult.model_validate(invalid_recurring)


def test_model_candidates_do_not_overwrite_existing_draft():
    draft = create_draft()
    draft.monthly_salary.value = 50_000
    draft.monthly_salary.source = "user_provided"
    draft.monthly_salary.confirmed = True
    result = FinancialExtractionResult.model_validate(empty_result(fields=[
        field_candidate("monthly_salary", 60_000, original_value="月薪六萬", original_amount=60_000)
    ]))
    updated = merge_extraction_candidates(draft, result, "月薪六萬")
    assert updated.monthly_salary.value == 50_000
    assert updated.conflicts


def test_allocation_percentages_are_calculated_by_backend_and_total_100():
    allocations = []
    for category, amount in (("food", 3333), ("transportation", 3333), ("other", 3334)):
        allocations.append({
            "category": category,
            "amount": amount,
            "percentage": None,
            "currency": "TWD",
            "source": "ai_estimated",
            "confidence": 0.7,
            "reason": "依使用者描述提出候選分配",
            "original_value": "生活費一萬元",
        })
    result = FinancialExtractionResult.model_validate(empty_result(
        fields=[field_candidate(
            "total_variable_expenses",
            10_000,
            original_value="生活費一萬元",
            original_amount=10_000,
        )],
        variable_expense_allocation=allocations,
    ))
    draft = merge_extraction_candidates(create_draft(), result, "生活費一萬元")
    assert sum(item.amount for item in draft.variable_expense_allocation) == 10_000
    assert round(sum(item.percentage for item in draft.variable_expense_allocation), 2) == 100
    assert all(not item.confirmed for item in draft.variable_expense_allocation)


def test_onboarding_endpoint_uses_mock_provider_without_api_key():
    payload = empty_result(fields=[
        field_candidate("cash_and_deposits", 500_000, original_value="存款五十萬", original_amount=500_000)
    ])
    provider = MockAIProvider({"存款五十萬": payload})
    app.dependency_overrides[get_onboarding_ai_provider] = lambda: provider
    try:
        response = TestClient(app).post(
            "/ai/financial-onboarding/message",
            json={"text": "存款五十萬"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["draft"]["cash_and_deposits"]["value"] == 500_000
    assert response.json()["provider_available"] is True
    runtime = json.loads(provider.calls[0]["user_prompt"].splitlines()[-1])
    assert set(runtime) == {
        "current_date",
        "current_question",
        "user_answer",
        "existing_values_for_conflict_detection",
        "existing_future_plans_for_conflict_detection",
    }
    assert runtime["existing_values_for_conflict_detection"] == {}


def test_onboarding_bare_amount_uses_current_question_without_model_guessing():
    provider = MockAIProvider({})
    app.dependency_overrides[get_onboarding_ai_provider] = lambda: provider
    try:
        first = TestClient(app).post(
            "/ai/financial-onboarding/message",
            json={"text": "100000"},
        ).json()
        second = TestClient(app).post(
            "/ai/financial-onboarding/message",
            json={"draft_id": first["draft"]["id"], "text": "50000"},
        ).json()
        third = TestClient(app).post(
            "/ai/financial-onboarding/message",
            json={"draft_id": first["draft"]["id"], "text": "6000"},
        ).json()
        fourth = TestClient(app).post(
            "/ai/financial-onboarding/message",
            json={"draft_id": first["draft"]["id"], "text": "3000"},
        ).json()
    finally:
        app.dependency_overrides.clear()

    assert provider.calls == []
    assert fourth["provider_available"] is True
    assert fourth["draft"]["fixed_expenses"]["value"] == 6000
    assert fourth["draft"]["total_variable_expenses"]["value"] == 3000
    assert fourth["draft"]["conflicts"] == []
    assert fourth["assistant_message"] == "想模擬未來幾年？"


def test_openai_provider_sends_strict_json_schema(monkeypatch):
    payload = empty_result()
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["request"] = kwargs
            return FakeResponse()

    monkeypatch.setattr(
        ai_provider_module,
        "settings",
        replace(ai_provider_module.settings, ai_api_key="test-only-key"),
    )
    monkeypatch.setattr(ai_provider_module.httpx, "AsyncClient", FakeClient)
    result = asyncio.run(
        OpenAIProvider().generate_structured(
            system_prompt="fixed prompt",
            user_prompt="runtime context",
            response_schema=FinancialExtractionResult,
        )
    )
    response_format = captured["request"]["json"]["response_format"]
    assert result == FinancialExtractionResult.model_validate(payload)
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"]["additionalProperties"] is False
