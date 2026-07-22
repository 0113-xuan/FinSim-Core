import asyncio

import pytest
from decimal import Decimal
from pydantic import ValidationError

from app.extraction_schemas import FinancialExtractionResult
from app.services.financial_answer_extraction import (
    ExtractionNormalizationError,
    deterministic_financial_extraction,
    extract_financial_answer,
)
from app.services.mock_ai_provider import MockAIProvider
from app.services.prompt_loader import load_prompt
from app.services.profile_onboarding import create_draft, merge_extraction_candidates
from app.schemas import ProfileValueSource


def result_payload(*, future_plans=None, debts=None, future_plan_conflicts=None):
    return {
        "fields": [],
        "variable_expense_allocation": [],
        "debts": debts or [],
        "future_plans": future_plans or [],
        "future_plan_conflicts": future_plan_conflicts or [],
        "ambiguities": [],
        "conflicts": [],
    }


def financing(
    *,
    is_financed=True,
    loan_amount=None,
    loan_term_months=None,
    annual_interest_rate=None,
    interest_rate_value=None,
    interest_rate_frequency=None,
    interest_rate_type=None,
    original_interest_rate_text=None,
):
    return {
        "is_financed": is_financed,
        "loan_amount": loan_amount,
        "loan_term_months": loan_term_months,
        "annual_interest_rate": annual_interest_rate,
        "interest_rate_value": interest_rate_value,
        "interest_rate_frequency": interest_rate_frequency,
        "interest_rate_type": interest_rate_type,
        "original_interest_rate_text": original_interest_rate_text,
    }


def vehicle_plan(
    source_text,
    *,
    target_text=None,
    normalized_target_date=None,
    estimated_cost=None,
    down_payment=None,
    plan_financing=None,
    currency="TWD",
    confirmed=True,
    confidence=0.95,
):
    return {
        "plan_type": "vehicle_purchase",
        "title": "購買汽車",
        "description": "購買一台汽車",
        "original_target_date_text": target_text,
        "normalized_target_date": normalized_target_date,
        "estimated_cost": estimated_cost,
        "down_payment": down_payment,
        "financing": plan_financing,
        "recurring_monthly_amount": None,
        "currency": currency,
        "source": "user_provided",
        "confirmed": confirmed,
        "confidence": confidence,
        "reason": "依使用者訊息直接擷取",
        "source_text": source_text,
    }


def extract_with_mock(message, payload, *, existing_future_plans=None):
    return asyncio.run(
        extract_financial_answer(
            provider=MockAIProvider({message: payload}),
            answer=message,
            current_values={},
            current_question=None,
            existing_future_plans=existing_future_plans,
        )
    )


def test_vehicle_purchase_with_installments_and_annual_rate():
    message = "我下個月要買一台60萬的車，分60期，利率3%。"
    payload = result_payload(future_plans=[vehicle_plan(
        message,
        target_text="下個月",
        normalized_target_date="2026-08",
        estimated_cost=600_000,
        currency="TWD",
        plan_financing=financing(
            loan_term_months=60,
            annual_interest_rate=3.0,
            interest_rate_frequency="annual",
            interest_rate_type="annual_percentage",
            original_interest_rate_text="利率3%",
        ),
    )])
    plan = extract_with_mock(message, payload).future_plans[0]
    assert plan.plan_type.value == "vehicle_purchase"
    assert plan.estimated_cost == 600_000
    assert plan.original_target_date_text == "下個月"
    assert plan.normalized_target_date == "2026-08"
    assert plan.down_payment is None
    assert plan.financing.loan_amount is None
    assert plan.financing.loan_term_months == 60
    assert plan.financing.annual_interest_rate == 3.0
    assert not hasattr(plan.financing, "monthly_payment")

    payload["future_plans"][0]["normalized_target_date"] = "2026-09"
    with pytest.raises(ExtractionNormalizationError):
        extract_with_mock(message, payload)


def test_vehicle_purchase_with_down_payment_does_not_derive_loan_amount():
    message = "我要買一台60萬的車，頭期20萬，其餘貸60期。"
    payload = result_payload(future_plans=[vehicle_plan(
        message,
        estimated_cost=600_000,
        down_payment=200_000,
        plan_financing=financing(loan_term_months=60),
    )])
    plan = extract_with_mock(message, payload).future_plans[0]
    assert plan.down_payment == 200_000
    assert plan.financing.loan_amount is None


def test_full_financing_preserves_explicit_loan_amount():
    message = "我要買一台60萬的車，全額貸款60期，利率3%。"
    payload = result_payload(future_plans=[vehicle_plan(
        message,
        estimated_cost=600_000,
        plan_financing=financing(
            loan_amount=600_000,
            loan_term_months=60,
            annual_interest_rate=3.0,
            interest_rate_frequency="annual",
            interest_rate_type="annual_percentage",
            original_interest_rate_text="利率3%",
        ),
    )])
    assert extract_with_mock(message, payload).future_plans[0].financing.loan_amount == 600_000


def test_existing_vehicle_loan_is_debt_not_future_plan():
    message = "我現在車貸還有60期，每月繳一萬一。"
    debt = {
        "debt_type": "auto_loan",
        "name": "車貸",
        "remaining_balance": None,
        "monthly_payment": 11_000,
        "annual_interest_rate": None,
        "remaining_months": 60,
        "currency": "TWD",
        "source": "user_provided",
        "confidence": 0.98,
        "reason": "貸款已經存在",
        "original_value": message,
    }
    result = extract_with_mock(message, result_payload(debts=[debt]))
    assert result.future_plans == []
    assert result.debts[0].debt_type.value == "auto_loan"


def test_deterministic_current_vehicle_loan_retains_exact_values_and_not_fixed_expense():
    message = "我現在車貸還有60期，每個月繳11000元"
    result = deterministic_financial_extraction(message)

    assert result is not None
    assert result.fields == []
    assert result.future_plans == []
    assert len(result.debts) == 1
    assert result.debts[0].debt_type.value == "auto_loan"
    assert result.debts[0].monthly_payment == 11_000
    assert result.debts[0].remaining_months == 60

    draft = create_draft()
    draft.fixed_expenses.value = 8_000
    draft.fixed_expenses.source = ProfileValueSource.user_provided
    draft.fixed_expenses.confirmed = True
    merged = merge_extraction_candidates(draft, result, message)

    assert merged.fixed_expenses.value == 8_000
    assert merged.monthly_debt_payments.value == Decimal("11000.00")
    assert merged.debts[0].monthly_payment.value == Decimal("11000.0")
    assert merged.debts[0].remaining_months.value == 60
    assert merged.future_plans == []
    assert merged.conflicts == []
    assert "2000" not in str(merged.model_dump())


def test_weekly_income_replaces_unconfirmed_zero_and_preserves_backend_provenance():
    message = "我每週打工賺5000元。"
    result = deterministic_financial_extraction(message)
    candidate = result.fields[0]

    assert candidate.original_amount == 5_000
    assert candidate.original_frequency.value == "weekly"
    assert candidate.value == 21_666.67

    draft = merge_extraction_candidates(create_draft(), result, message)
    field = draft.other_recurring_income
    assert draft.conflicts == []
    assert field.value == Decimal("21666.67")
    assert field.original_amount == 5_000
    assert field.original_frequency == "weekly"
    assert field.normalization_source == "backend_calculation"
    assert field.source.value == "backend_normalized"
    assert field.confirmed is False


def test_weekly_income_conflicts_with_user_confirmed_zero():
    message = "我每週打工賺5000元。"
    result = deterministic_financial_extraction(message)
    draft = create_draft()
    draft.other_recurring_income.value = 0
    draft.other_recurring_income.source = ProfileValueSource.user_provided
    draft.other_recurring_income.confirmed = True

    merged = merge_extraction_candidates(draft, result, message)

    assert merged.other_recurring_income.value == 0
    assert merged.conflicts
    assert "21666.67" in merged.conflicts[0]


def test_deterministic_vehicle_plan_boundaries_and_missing_values():
    next_month = deterministic_financial_extraction("我下個月想買一台60萬的車。").future_plans[0]
    assert next_month.plan_type.value == "vehicle_purchase"
    assert next_month.estimated_cost == 600_000
    assert next_month.original_target_date_text == "下個月"
    assert next_month.normalized_target_date is not None
    assert next_month.financing is None

    down_payment = deterministic_financial_extraction(
        "我要買一台60萬的車，頭期20萬，剩下貸60期。"
    ).future_plans[0]
    assert down_payment.estimated_cost == 600_000
    assert down_payment.down_payment == 200_000
    assert down_payment.financing.is_financed is True
    assert down_payment.financing.loan_term_months == 60
    assert down_payment.financing.loan_amount is None

    full = deterministic_financial_extraction(
        "我要買一台60萬的車，全額貸款60期，年利率3%。"
    ).future_plans[0]
    assert full.financing.loan_amount == 600_000
    assert full.financing.loan_term_months == 60
    assert full.financing.annual_interest_rate == 3


def test_vague_financing_keeps_unknown_values_null():
    message = "我明年可能想買車，應該會貸款。"
    payload = result_payload(future_plans=[vehicle_plan(
        message,
        target_text="明年",
        plan_financing=financing(),
        confirmed=False,
        confidence=0.62,
    )])
    plan = extract_with_mock(message, payload).future_plans[0]
    assert plan.estimated_cost is None
    assert plan.down_payment is None
    assert plan.financing.loan_amount is None
    assert plan.financing.loan_term_months is None
    assert plan.financing.annual_interest_rate is None
    assert plan.confirmed is False


def test_monthly_interest_is_not_converted_to_annual():
    message = "車貸月利率0.3%，分60期。"
    payload = result_payload(future_plans=[vehicle_plan(
        message,
        plan_financing=financing(
            loan_term_months=60,
            interest_rate_value=0.3,
            interest_rate_frequency="monthly",
            interest_rate_type="stated_percentage",
            original_interest_rate_text="月利率0.3%",
        ),
    )])
    terms = extract_with_mock(message, payload).future_plans[0].financing
    assert terms.interest_rate_value == 0.3
    assert terms.interest_rate_frequency.value == "monthly"
    assert terms.annual_interest_rate is None


def test_unqualified_currency_defaults_to_twd_and_unexpected_payment_is_rejected():
    message = "我要買一台60萬的車。"
    plan = vehicle_plan(message, estimated_cost=600_000, currency="TWD")
    assert extract_with_mock(
        message,
        result_payload(future_plans=[plan]),
    ).future_plans[0].currency.value == "TWD"

    plan["financing"] = {
        **financing(loan_term_months=60),
        "monthly_payment": 10_000,
    }
    with pytest.raises(ValidationError):
        FinancialExtractionResult.model_validate(
            result_payload(future_plans=[plan])
        )


def test_future_plan_conflict_is_strict_and_requires_confirmation():
    conflict = {
        "field": "future_plans[0].estimated_cost",
        "existing_value": 500_000,
        "candidate_value": 600_000,
        "reason": "使用者提供不同的購車預算",
        "requires_user_confirmation": True,
    }
    result = FinancialExtractionResult.model_validate(
        result_payload(future_plan_conflicts=[conflict])
    )
    assert result.future_plan_conflicts[0].candidate_value == 600_000

    conflict["requires_user_confirmation"] = False
    with pytest.raises(ValidationError):
        FinancialExtractionResult.model_validate(
            result_payload(future_plan_conflicts=[conflict])
        )


def test_prompt_separates_future_financing_from_existing_debt():
    prompt = load_prompt("financial_answer_extraction.md")
    assert "not `debts`, when the loan" in prompt
    assert "A loan that already exists belongs under `debts`" in prompt
    assert "monthly repayment" in prompt
    assert "Never assume zero down payment" in prompt
