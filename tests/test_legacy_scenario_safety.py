import logging

import pytest

from app.core.transparency import build_simulation_transparency, display_source_label
from app.schemas import ScenarioParseRequest
from app.services.ai_provider import UnsupportedAIProviderOperation
from app.services.optimizer import find_baseline_option
from app.services.scenario_parser import deterministic_parse_scenario, parse_scenario


@pytest.mark.parametrize(
    "position",
    ["first", "middle", "last"],
)
def test_baseline_lookup_is_independent_of_position(position):
    baseline = {"name": "Baseline", "score": 10}
    other = [{"name": "Reduce expenses", "score": 1}, {"name": "Increase income", "score": 2}]
    if position == "first":
        options = [baseline, *other]
    elif position == "middle":
        options = [other[0], baseline, other[1]]
    else:
        options = [*other, baseline]
    assert find_baseline_option(options) is baseline


def test_baseline_lookup_survives_sorting():
    options = [
        {"name": "Baseline", "score": 10},
        {"name": "Reduce expenses", "score": 1},
        {"name": "Increase income", "score": 2},
    ]
    sorted_options = sorted(options, key=lambda item: item["score"])
    assert find_baseline_option(sorted_options)["name"] == "Baseline"


def test_baseline_lookup_rejects_missing_duplicate_and_similar_names():
    with pytest.raises(ValueError, match="missing"):
        find_baseline_option([{"name": "Baseline projection"}])
    with pytest.raises(ValueError, match="multiple"):
        find_baseline_option([{"name": "Baseline"}, {"name": "Baseline"}])
    with pytest.raises(ValueError, match="missing"):
        find_baseline_option([{"name": "Not Baseline"}])


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("manual", "使用者提供"),
        ("user_provided", "使用者提供"),
        ("system_assumption", "系統模擬假設"),
        ("ai", "AI 語意解析"),
        ("derived", "系統計算"),
        ("backend_normalized", "系統計算"),
        ("external_estimate", "外部資料估算"),
        ("unexpected", "來源未標示"),
        (None, "來源未標示"),
    ],
)
def test_transparency_source_mapping(source, expected):
    assert display_source_label(source) == expected


def test_reason_does_not_override_manual_source():
    baseline_row = {
        "expense_categories": [{"category": "food", "amount": 1000}],
        "expense": 1000,
        "debt_payment": 0,
        "net_cashflow": 0,
    }
    scenario_row = {
        "expense_categories": [{"category": "food", "amount": 1500}],
        "expense": 1500,
        "debt_payment": 0,
        "net_cashflow": -500,
    }
    result = build_simulation_transparency(
        profile={"variable_expense_model": {"mode": "advanced", "categories": [{"category": "food"}]}},
        events=[{
            "type": "life_event",
            "name": "Manual food change",
            "start_month": 1,
            "category_monthly_adjustment": 500,
            "target_expense_category": "food",
            "source": "manual",
            "display_source": "AI 推估",
            "reason": "The user entered this reason",
        }],
        loans=[],
        random_shocks=[],
        baseline_result={"simulation_curve": [baseline_row], "summary": {}},
        scenario_result={"simulation_curve": [scenario_row], "summary": {}},
    )
    food = next(
        item for item in result["expense_comparison"] if item["category"] == "food"
    )
    assert food["source"] == "使用者提供"
    assert result["events"][0]["source"] == "使用者提供"


def test_deterministic_values_are_traceable_system_assumptions():
    parsed = deterministic_parse_scenario(ScenarioParseRequest(
        text="move to Taipei, gym, travel to Japan, buy a car, and change job",
        months=60,
    ))
    assert parsed.provider_used is False
    assert parsed.fallback_used is True
    assert parsed.fallback_type == "deterministic_system_assumptions"
    assert parsed.fallback_reason == "provider_unavailable"
    assert parsed.events
    assert parsed.expense_adjustments
    assert all(item.source.value == "system_assumption" for item in parsed.events)
    assert all(item.display_source == "系統模擬假設" for item in parsed.events)
    assert all(item.assumption_key for item in parsed.events)
    assert all(item.source == "system_assumption" for item in parsed.expense_adjustments)
    assert all(item.assumption_key for item in parsed.expense_adjustments)
    assert all(source.source != "AI 推估" for source in parsed.display.sources)


def test_unsupported_provider_operation_uses_observable_safe_fallback(monkeypatch, caplog):
    class UnsupportedProvider:
        def complete_json(self, *, system, user):
            raise UnsupportedAIProviderOperation(
                "secret provider detail fake-api-key"
            )

    user_text = "buy a car with private financial details"
    monkeypatch.setattr(
        "app.services.scenario_parser.get_ai_provider",
        lambda: UnsupportedProvider(),
    )
    with caplog.at_level(logging.WARNING):
        parsed = parse_scenario(ScenarioParseRequest(text=user_text, months=12))

    assert parsed.provider_used is False
    assert parsed.fallback_used is True
    assert parsed.fallback_reason == "unsupported_operation"
    assert "error_type=unsupported_operation" in caplog.text
    assert user_text not in caplog.text
    assert "secret provider detail" not in caplog.text
    assert "fake-api-key" not in caplog.text


def test_valid_provider_result_is_not_marked_as_fallback(monkeypatch):
    class ValidProvider:
        def complete_json(self, *, system, user):
            return {
                "summary": "validated result",
                "expense_adjustments": [],
                "events": [{
                    "type": "life_event",
                    "name": "Parsed event",
                    "start_month": 2,
                    "source": "ai",
                }],
                "confidence": 0.8,
                "warnings": [],
            }

    monkeypatch.setattr(
        "app.services.scenario_parser.get_ai_provider",
        lambda: ValidProvider(),
    )
    parsed = parse_scenario(ScenarioParseRequest(text="change job soon", months=12))
    assert parsed.provider_used is True
    assert parsed.fallback_used is False
    assert parsed.fallback_type is None
    assert parsed.fallback_reason is None
    assert parsed.events[0].source.value == "ai"
    assert parsed.display.sources[1].source == "AI 語意解析"
