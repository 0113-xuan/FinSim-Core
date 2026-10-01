from datetime import date
from decimal import Decimal

import pytest

from app.schemas import ScenarioParseRequest
from app.services.calendar_period import (
    YearMonth,
    extract_date_text,
    normalize_date_text,
    period_for_simulation_month,
    resolve_reference_date,
    simulation_month_for_period,
)
from app.services.financial_answer_extraction import deterministic_financial_extraction
from app.services.profile_onboarding import create_draft, merge_extraction_candidates
from app.services.scenario_parser import deterministic_parse_scenario


REFERENCE_DATE = date(2026, 7, 21)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("下個月", "2026-08"),
        ("兩個月後", "2026-09"),
        ("半年後", "2027-01"),
        ("六個月後", "2027-01"),
        ("6個月後", "2027-01"),
        ("十二個月後", "2027-07"),
        ("今年年底", "2026-12"),
        ("2027年3月", "2027-03"),
        ("明年", "2027-01"),
        ("明年年初", "2027-01"),
        ("明年3月", "2027-03"),
    ],
)
def test_calendar_normalization(text, expected):
    assert normalize_date_text(text, REFERENCE_DATE) == expected


def test_calendar_rollover_leap_year_and_vague_date():
    assert normalize_date_text("下個月", date(2026, 12, 10)) == "2027-01"
    assert YearMonth(2028, 1).add_months(1) == YearMonth(2028, 2)
    assert normalize_date_text("過一陣子", REFERENCE_DATE) is None
    assert simulation_month_for_period("2026-08", REFERENCE_DATE) == 1
    assert period_for_simulation_month(1, REFERENCE_DATE) == "2026-08"
    assert extract_date_text("先說兩個月後，後來改成半年後") == "半年後"


def test_timezone_and_reference_date_are_injectable():
    assert resolve_reference_date(REFERENCE_DATE, "Asia/Taipei") == REFERENCE_DATE
    with pytest.raises(ValueError, match="時區"):
        resolve_reference_date(None, "Invalid/Timezone")


@pytest.mark.parametrize(
    "message",
    [
        "我打工每兩週領9000元。",
        "我每隔兩週領薪水9000元。",
        "我打工兩週領一次9000元。",
        "我隔週領9000元。",
        "我雙週薪9000元。",
    ],
)
def test_biweekly_income_variants_are_backend_normalized(message):
    result = deterministic_financial_extraction(message, current_date=REFERENCE_DATE)
    field = result.fields[0]
    assert field.original_amount == 9000
    assert field.original_frequency.value == "biweekly"
    assert Decimal(str(field.value)) == Decimal("19500.00")
    assert "26 ÷ 12" in field.normalized_from


def test_biweekly_income_replaces_only_unconfirmed_default_zero():
    message = "我打工每兩週領9000元。"
    result = deterministic_financial_extraction(message, current_date=REFERENCE_DATE)
    merged = merge_extraction_candidates(create_draft(), result, message)
    assert Decimal(str(merged.other_recurring_income.value)) == Decimal("19500.00")
    assert merged.other_recurring_income.source.value == "backend_normalized"
    assert not merged.conflicts


def parse(text: str, profile=None):
    return deterministic_parse_scenario(
        ScenarioParseRequest(
            text=text,
            months=60,
            reference_date=REFERENCE_DATE,
            timezone="Asia/Taipei",
        ),
        confirmed_profile=profile,
    )


def known(result):
    return {item.key: item for item in result.clarification.known_values}


def test_cash_used_car_keeps_price_payment_and_calendar_date():
    result = parse("我今年年底想用現金買一台25萬的二手車。")
    values = known(result)
    assert values["purchase_price"].value == "NT$250,000"
    assert values["vehicle_condition"].value == "二手車"
    assert values["payment_method"].value == "現金一次付清"
    assert values["normalized_timing"].value == "2026年12月"
    assert "timing" not in result.clarification.missing_fields
    assert not any("貸款" in question or "什麼時候" in question for question in result.clarification.questions)


def test_relocation_separates_inputs_and_does_not_invent_one_time_cost():
    result = parse("我下個月要搬家，新房租每月多5000元，但交通費會少2000元。")
    values = known(result)
    assert values["timing"].value.startswith("2026年08月")
    assert values["rent_change"].value == "+NT$5,000"
    assert values["commute_change"].value == "-NT$2,000"
    assert values["net_cash_flow"].value == "-NT$3,000"
    assert values["net_cash_flow"].source == "系統計算"
    assert result.events == []
    assert "one_time_costs" in result.clarification.missing_fields
    assert "30,000" not in str(result.model_dump())


def test_complete_relocation_preserves_actual_one_time_costs():
    result = parse("我今年12月要搬家，目前房租9000，新房租14000，押金28000，搬家費6000，通勤每月省2500元。")
    assert result.clarification is None
    assert result.display.start_period == "2026-12"
    assert result.display.one_time_cost == 34000
    assert len(result.expense_adjustments) == 2
    assert {item.monthly_amount for item in result.expense_adjustments} == {5000, -2500}


def test_insurance_affordability_without_profile_requests_minimum_profile():
    result = parse("我想買保險，但不知道自己負擔得起多少。")
    assert result.clarification.intent == "insurance_purchase"
    assert "monthly_income" in result.clarification.missing_fields
    assert "系統模擬假設" in result.clarification.system_assumption_offer
    assert "找不到" not in result.clarification.summary


def test_insurance_affordability_with_profile_generates_labeled_candidates():
    result = parse(
        "我想買保險，但不知道自己負擔得起多少。",
        profile={"salary": 60000, "fixed_expense": 25000, "variable_expense": 15000, "balance": 300000},
    )
    values = known(result)
    assert values["disposable_cash_flow"].value == "NT$20,000"
    assert values["baseline"].value == "不新增保費（NT$0）"
    candidates = [item for key, item in values.items() if key.startswith("premium_candidate_")]
    assert len(candidates) == 3
    assert all(item.source == "系統模擬假設" for item in candidates)


def test_annual_insurance_premium_preserves_original_and_backend_average():
    result = parse("我想買醫療險，一年保費24000元。")
    values = known(result)
    assert values["annual_premium"].value == "NT$24,000"
    assert values["monthly_average"].value == "NT$2,000"
    assert values["monthly_average"].source == "系統計算"
    assert result.clarification.missing_fields == ["timing"]


def test_monthly_insurance_scenario_uses_real_calendar_period():
    result = parse("如果我下個月開始每月繳3000元醫療保險，五年後會差多少？")
    assert result.clarification is None
    assert result.display.start_period == "2026-08"
    assert result.events[0].monthly_amount == -3000
    assert "一定" not in result.summary


def test_explicit_vehicle_month_and_calendar_planning_boundaries():
    vehicle = parse("我明年3月想買一台80萬的車。")
    assert known(vehicle)["normalized_timing"].value == "2027年03月"
    savings = parse("我明年1月開始每月多存5000元。")
    assert known(savings)["timing"].value == "2027年01月"
    work_break = parse("我2027年2月想停工三個月。")
    values = known(work_break)
    assert values["start_period"].value == "2027年02月"
    assert values["end_period"].value == "2027年4月（含）"


def test_vague_job_change_keeps_timing_unknown():
    result = parse("我過一陣子想換工作。")
    assert result.clarification.intent == "job_change"
    assert "timing" in result.clarification.missing_fields
    assert "什麼時候" in result.clarification.questions[0]
    assert "第 6 個月" not in str(result.model_dump())
