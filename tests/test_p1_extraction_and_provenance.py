from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.schemas import ScenarioParseRequest
from app.services.financial_amount import parse_financial_amount
from app.services.financial_answer_extraction import (
    deterministic_financial_extraction,
    find_vehicle_price_candidate,
)
from app.services.scenario_parser import deterministic_parse_scenario
from app.services.rate_limit import ai_rate_limiter
from main import app


REFERENCE_DATE = date(2026, 7, 21)
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_test_rate_limit():
    ai_rate_limiter.hits.clear()


def parse(text: str):
    return deterministic_parse_scenario(ScenarioParseRequest(
        text=text,
        months=60,
        reference_date=REFERENCE_DATE,
        timezone="Asia/Taipei",
    ))


def known(result):
    return {item.key: item for item in result.clarification.known_values}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("兩千", 2_000),
        ("五千", 5_000),
        ("一萬", 10_000),
        ("一萬二", 12_000),
        ("一萬二千", 12_000),
        ("二萬五", 25_000),
        ("二萬五千", 25_000),
        ("十萬", 100_000),
        ("二十五萬", 250_000),
        ("25萬", 250_000),
        ("1萬2", 12_000),
    ],
)
def test_reusable_chinese_financial_amount_parser(text, expected):
    parsed = parse_financial_amount(text)
    assert parsed.value == Decimal(expected)
    assert parsed.original_text == text


@pytest.mark.parametrize("text", ["兩週", "60期", "一萬二五", "萬萬"])
def test_financial_amount_parser_rejects_non_money_or_ambiguous_text(text):
    with pytest.raises(ValueError):
        parse_financial_amount(text)


@pytest.mark.parametrize(
    "text",
    [
        "我年底打算拿25萬元現金買二手車",
        "我年底想花25萬現金買二手車",
        "我打算年底用25萬元買一台二手車",
        "年底想現金買二手車，預算25萬",
        "我想在年底現金買一台二手車，價格大概25萬",
    ],
)
def test_cash_used_vehicle_paraphrases_have_same_semantics(text):
    result = parse(text)
    values = known(result)
    assert result.clarification.intent == "vehicle_purchase"
    assert values["purchase_price"].value == "NT$250,000"
    assert values["vehicle_condition"].value == "二手車"
    assert values["payment_method"].value == "現金一次付清"
    assert values["normalized_timing"].value == "2026年12月"
    assert not any(field in result.clarification.missing_fields for field in (
        "timing", "down_payment", "loan_term", "interest_rate"
    ))
    assert not any("什麼時候" in question or "貸款" in question for question in result.clarification.questions)


@pytest.mark.parametrize(
    ("text", "price", "period"),
    [
        ("我2027年2月想買二手車，預算1800元", "NT$1,800", "2027年02月"),
        ("我2028年3月想買二手車，預算25萬", "NT$250,000", "2028年03月"),
        ("我明年想買二手車，預算1800元", "NT$1,800", "2027年01月"),
        ("我想在2027年買一台車，里程大約10000公里，預算20萬", "NT$200,000", None),
    ],
)
def test_vehicle_price_excludes_date_and_mileage_numbers(text, price, period):
    values = known(parse(text))
    assert values["purchase_price"].value == price
    if period:
        assert values["normalized_timing"].value == period


def test_vehicle_price_excludes_loan_term_and_interest_rate():
    result = parse("我想買一台60萬的車，貸60期，年利率3%")
    values = known(result)
    assert values["purchase_price"].value == "NT$600,000"
    assert values["loan_term"].value == "60 期"
    assert values["interest_rate"].value == "3%"


def test_vehicle_price_prefers_vehicle_price_over_monthly_affordability():
    values = known(parse("我每月可以負擔1800元，但想買一台25萬的車"))
    assert values["purchase_price"].value == "NT$250,000"


@pytest.mark.parametrize(
    "text",
    [
        "我2027年2月想買二手車，但還不知道預算",
        "我想在2027年2月買一台車",
    ],
)
def test_unknown_vehicle_price_does_not_use_date_numbers(text):
    result = parse(text)
    assert "purchase_price" in result.clarification.missing_fields
    assert "purchase_price" not in known(result)
    assert any("預算" in question or "車價" in question for question in result.clarification.questions)


def test_vehicle_price_candidate_filter_rejects_non_price_numeric_contexts():
    assert find_vehicle_price_candidate("2027年2月，貸60期，年利率3%，里程10000公里") is None


@pytest.mark.parametrize(
    "text",
    [
        "打算年底買二手車，現金預算大約25萬元",
        "我年底想買二手車，預算大概25萬",
        "我年底想買二手車，預算約25萬",
        "我年底想買二手車，預算25萬左右",
        "我年底想買二手車，車價大約25萬元",
        "我年底想買二手車，價格約莫25萬元",
    ],
)
def test_vehicle_price_approximation_phrases_preserve_price(text):
    result = parse(text)
    values = known(result)
    assert result.clarification.intent == "vehicle_purchase"
    assert values["purchase_price"].value == "NT$250,000"
    assert "purchase_price" not in result.clarification.missing_fields
    assert not any("購車預算" in question for question in result.clarification.questions)


def test_cash_vehicle_price_with_approximation_preserves_full_context():
    result = parse("打算年底買二手車，現金預算大約25萬元")
    values = known(result)
    assert values["vehicle_condition"].value == "二手車"
    assert values["payment_method"].value == "現金一次付清"
    assert values["normalized_timing"].value == "2026年12月"
    assert "loan_term" not in values
    assert not any("購車預算" in question or "貸款" in question for question in result.clarification.questions)
    extraction = deterministic_financial_extraction(
        "打算年底買二手車，現金預算大約25萬元",
        current_date=REFERENCE_DATE,
    )
    assert extraction.future_plans[0].financing is None


def test_approximation_without_price_keyword_remains_unknown():
    result = parse("我年底想買二手車，大概需要25萬元")
    assert "purchase_price" in result.clarification.missing_fields
    assert "purchase_price" not in known(result)


def test_approximate_small_price_does_not_select_explicit_date_numbers():
    values = known(parse("我2027年2月想買二手車，預算大約1800元"))
    assert values["purchase_price"].value == "NT$1,800"
    assert values["normalized_timing"].value == "2027年02月"


def test_approximate_monthly_payment_does_not_replace_vehicle_price():
    values = known(parse("我2027年想買二手車，每月大約可以繳2000元，車價約25萬"))
    assert values["purchase_price"].value == "NT$250,000"


def test_approximate_mileage_does_not_replace_vehicle_price():
    values = known(parse("我想買二手車，里程大約10萬公里，預算大約25萬"))
    assert values["purchase_price"].value == "NT$250,000"


@pytest.mark.parametrize("phrase", ["差不多", "大致", "估計", "預計"])
def test_supported_approximation_synonyms_share_vehicle_price_rule(phrase):
    candidate = find_vehicle_price_candidate(f"買二手車，預算{phrase}25萬")
    assert candidate is not None
    assert candidate.value == Decimal(250_000)


@pytest.mark.parametrize(
    ("text", "rent", "commute", "cashflow", "period"),
    [
        ("下個月搬家後，租金增加五千，通勤可以省兩千。", 5_000, -2_000, -3_000, "2026年08月"),
        ("下個月搬家，房租多6000，通勤費少2500。", 6_000, -2_500, -3_500, "2026年08月"),
        ("兩個月後搬家，租屋費增加一萬二，車資可以省三千。", 12_000, -3_000, -9_000, "2026年09月"),
        ("搬家後租金變便宜五千，但通勤成本增加兩千。", -5_000, 2_000, 3_000, None),
    ],
)
def test_relocation_synonyms_chinese_amounts_and_directions(text, rent, commute, cashflow, period):
    result = parse(text)
    values = known(result)
    assert values["rent_change"].value == f"{'+' if rent >= 0 else '-'}NT${abs(rent):,.0f}"
    assert values["commute_change"].value == f"{'+' if commute >= 0 else '-'}NT${abs(commute):,.0f}"
    assert values["net_cash_flow"].value == f"{'+' if cashflow >= 0 else '-'}NT${abs(cashflow):,.0f}"
    assert values["net_cash_flow"].source == "系統計算"
    if period:
        assert values["timing"].value.startswith(period)
    assert "30,000" not in str(result.model_dump())


def test_user_insurance_candidates_keep_user_provenance_and_derived_totals():
    result = parse("我想比較每月保費1000、2000和3000元，哪個比較不影響生活？")
    candidates = result.clarification.candidates
    assert [item.monthly_amount for item in candidates] == [1000, 2000, 3000]
    assert all(item.source == "user_provided" for item in candidates)
    assert all(item.display_source == "使用者提供" for item in candidates)
    assert [item.derived_total for item in candidates] == [60000, 120000, 180000]
    assert all(item.derived_source == "derived" for item in candidates)
    assert all(item.derived_display_source == "系統計算" for item in candidates)


def test_mixed_insurance_candidates_keep_distinct_provenance():
    result = parse("我想比較每月保費1000和2000元，另外請系統幫我加一個其他方案。")
    candidates = result.clarification.candidates
    assert [(item.monthly_amount, item.source) for item in candidates] == [
        (1000, "user_provided"),
        (2000, "user_provided"),
        (1500, "system_assumption"),
    ]


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("我年底打算拿25萬元現金買二手車", "vehicle_purchase"),
        ("下個月搬家後，租金增加五千，通勤可以省兩千。", "relocation"),
        ("我想比較每月保費1000、2000和3000元，哪個比較不影響生活？", "insurance_purchase"),
    ],
)
def test_p1_api_returns_structured_non_generic_response(text, intent):
    response = client.post("/ai/parse-scenario", json={
        "text": text,
        "months": 60,
        "reference_date": "2026-07-21",
        "timezone": "Asia/Taipei",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["clarification"]["intent"] == intent
    assert "找不到" not in body["clarification"]["summary"]


def test_p1_api_exposes_candidate_sources():
    response = client.post("/ai/parse-scenario", json={
        "text": "我想比較每月保費1000和2000元，另外請系統幫我加一個其他方案。",
        "months": 60,
        "reference_date": "2026-07-21",
        "timezone": "Asia/Taipei",
    })
    candidates = response.json()["clarification"]["candidates"]
    assert [item["source"] for item in candidates] == [
        "user_provided", "user_provided", "system_assumption"
    ]
    assert all(item["derived_source"] == "derived" for item in candidates)
