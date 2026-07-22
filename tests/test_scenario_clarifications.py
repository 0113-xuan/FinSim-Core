from app.schemas import ScenarioParseRequest
from app.services.scenario_parser import (
    LEGACY_VEHICLE_MAINTENANCE_ANNUAL,
    deterministic_parse_scenario,
)


def parse(text: str):
    return deterministic_parse_scenario(ScenarioParseRequest(text=text, months=60))


def test_unspecified_vehicle_timing_requests_clarification_without_month_six_default():
    result = parse("我想買車，幫我看看會有什麼影響")

    assert result.events == []
    assert result.display is None
    assert result.clarification.intent == "vehicle_purchase"
    assert "timing" in result.clarification.missing_fields
    assert result.clarification.questions == ["預計什麼時候買車？"]
    assert "第 6 個月" not in str(result.model_dump())
    assert "系統模擬假設" in result.clarification.system_assumption_offer
    assert "年度預算" in result.clarification.system_assumption_offer


def test_relocation_uses_scenario_specific_questions():
    result = parse("我想搬到離公司近一點的地方。")

    assert result.events == []
    assert result.clarification.intent == "relocation"
    assert result.clarification.missing_fields == [
        "timing",
        "current_rent",
        "new_rent",
        "one_time_costs",
        "commuting_cost_change",
    ]
    questions = " ".join(result.clarification.questions)
    assert "什麼時候搬家" in questions
    assert "目前房租" in questions
    assert "新房租" in questions
    assert "押金、仲介費或搬家費" in questions
    assert "通勤費" in questions
    assert "找不到" not in result.clarification.summary


def test_vehicle_next_month_acknowledges_price_and_requests_financing():
    result = parse("我下個月想買一台60萬的車。")
    values = {item.key: item.value for item in result.clarification.known_values}

    assert values["purchase_price"] == "NT$600,000"
    assert values["timing"] == "下個月"
    assert result.clarification.missing_fields == [
        "payment_method",
        "down_payment",
        "loan_term",
        "interest_rate",
    ]
    assert "現金一次付清" in " ".join(result.clarification.questions)


def test_vehicle_down_payment_requests_only_interest_and_timing():
    result = parse("我要買一台60萬的車，頭期20萬，剩下貸60期。")
    values = {item.key: item.value for item in result.clarification.known_values}

    assert values["purchase_price"] == "NT$600,000"
    assert values["down_payment"] == "NT$200,000"
    assert values["loan_term"] == "60 期"
    assert result.clarification.missing_fields == ["timing", "interest_rate"]
    assert "車貸年利率" in " ".join(result.clarification.questions)


def test_full_financing_requests_only_timing():
    result = parse("我要買一台60萬的車，全額貸款60期，年利率3%。")
    values = {item.key: item.value for item in result.clarification.known_values}

    assert values["loan_amount"] == "NT$600,000"
    assert values["loan_term"] == "60 期"
    assert values["interest_rate"] == "3%"
    assert result.clarification.missing_fields == ["timing"]
    assert result.clarification.questions == ["預計什麼時候買車？"]


def test_complete_vehicle_plan_preserves_annual_maintenance_assumption():
    result = parse("我下個月要買一台60萬的車，全額貸款60期，年利率3%。")
    maintenance = next(item for item in result.events if item.name == "車輛維護規劃平均")
    assumptions = {item.key: item for item in result.display.assumptions}

    assert result.clarification is None
    assert maintenance.category_monthly_adjustment == 1_500
    assert maintenance.source.value == "system_assumption"
    assert "不代表每月實際保養" in maintenance.reason
    assert LEGACY_VEHICLE_MAINTENANCE_ANNUAL == 18_000
    assert assumptions["vehicle_maintenance_annual_budget"].value == "NT$18,000 / 年"
    assert assumptions["vehicle_maintenance_annual_budget"].source == "系統模擬假設"
    assert assumptions["vehicle_maintenance_monthly_average"].value.startswith("NT$1,500 / 月")
    assert assumptions["vehicle_maintenance_monthly_average"].source == "系統計算"
