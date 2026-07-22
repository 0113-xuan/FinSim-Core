from fastapi.testclient import TestClient
from importlib import import_module
from app.services.ai_provider import UnsupportedAIProviderOperation

from main import app


client = TestClient(app)


def payload():
    return {
        "profile": {
            "salary": 60000,
            "fixed_expense": 20000,
            "variable_expense": 15000,
            "balance": 1000000,
            "target_emergency_months": 6,
        },
        "months": 12,
        "seed": 42,
    }


def test_simulate_endpoint():
    response = client.post("/simulate", json=payload())
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data["result"]
    assert "simulation_curve" in data["result"]
    assert "transparency" in data["result"]


def test_simulation_transparency_supports_multiple_scenarios_and_expense_sources():
    body = {
        **payload(),
        "events": [
            {
                "type": "life_event",
                "name": "Travel food",
                "start_month": 2,
                "category_monthly_adjustment": 1500,
                "target_expense_category": "food",
                "source": "ai",
                "reason": "旅遊期間餐飲增加",
                "display_source": "AI 推估",
            },
            {
                "type": "life_event",
                "name": "Daily food offset",
                "start_month": 2,
                "category_monthly_adjustment": -500,
                "target_expense_category": "food",
                "expense_role": "offset",
                "source": "ai",
                "reason": "原本日常餐飲減少",
                "display_source": "AI 推估",
            },
        ],
        "scenario_context": [
            {"id": "travel", "title": "日本旅行", "status": "使用者已確認"},
            {"id": "move", "title": "搬家", "status": "等待確認"},
        ],
    }
    response = client.post("/simulate", json=body)
    assert response.status_code == 200
    transparency = response.json()["result"]["transparency"]
    assert len(transparency["scenarios"]) == 2
    assert round(sum(item["percentage"] for item in transparency["expense_allocation"]), 2) == 100
    food = next(item for item in transparency["expense_comparison"] if item["category"] == "food")
    assert food["adjusted_amount"] - food["original_amount"] == 1000
    assert food["source"] == "AI 語意解析"
    assert transparency["cost_breakdown"]["recurring_scenario_expenses"] == 1500
    assert transparency["cost_breakdown"]["offsets"] == 500
    assert transparency["cost_breakdown"]["net_monthly_change"] == 1000
    assert transparency["financial_impact"]["final_assets"]["after"] is not None


def test_monte_carlo_endpoint():
    body = {**payload(), "simulations": 10, "sample_paths": 2}
    response = client.post("/monte-carlo", json=body)
    assert response.status_code == 200
    assert "percentiles" in response.json()


def test_ai_parse_endpoint_fallback():
    response = client.post("/ai/parse-scenario", json={"text": "move to Taipei and travel to Japan", "months": 60})
    assert response.status_code == 200
    assert "events" in response.json()
    assert response.json()["provider_used"] is False
    assert response.json()["fallback_used"] is True
    assert response.json()["fallback_type"] == "deterministic_system_assumptions"


def test_ai_parse_endpoint_returns_structured_vehicle_and_relocation_clarifications(monkeypatch):
    monkeypatch.setattr("app.services.scenario_parser.get_ai_provider", lambda: None)
    cases = [
        (
            "我下個月想買一台60萬的車。",
            "vehicle_purchase",
            ["payment_method", "down_payment", "loan_term", "interest_rate"],
        ),
        (
            "我要買一台60萬的車，頭期20萬，剩下貸60期。",
            "vehicle_purchase",
            ["timing", "interest_rate"],
        ),
        (
            "我要買一台60萬的車，全額貸款60期，年利率3%。",
            "vehicle_purchase",
            ["timing"],
        ),
        (
            "我想搬到離公司近一點的地方。",
            "relocation",
            ["timing", "current_rent", "new_rent", "one_time_costs", "commuting_cost_change"],
        ),
    ]

    for text, intent, missing_fields in cases:
        response = client.post("/ai/parse-scenario", json={"text": text, "months": 60})
        body = response.json()
        assert response.status_code == 200
        assert body["clarification"]["intent"] == intent
        assert body["clarification"]["missing_fields"] == missing_fields
        assert body["events"] == []
        assert "找不到" not in body["clarification"]["summary"]


def test_legacy_scenario_route_is_deprecated_and_does_not_persist():
    from main import CONFIRMED_DEMO_PROFILES, PROFILES, PROFILE_DRAFTS

    before = (dict(PROFILES), dict(PROFILE_DRAFTS), dict(CONFIRMED_DEMO_PROFILES))
    response = client.post(
        "/ai/parse-scenario",
        json={"text": "buy a car and travel to Japan", "months": 60},
    )
    after = (dict(PROFILES), dict(PROFILE_DRAFTS), dict(CONFIRMED_DEMO_PROFILES))

    assert response.status_code == 200
    assert after == before
    assert app.openapi()["paths"]["/ai/parse-scenario"]["post"]["deprecated"] is True


def test_legacy_provider_failure_does_not_leak_to_api_or_logs(monkeypatch, caplog):
    class UnsupportedProvider:
        def complete_json(self, *, system, user):
            raise UnsupportedAIProviderOperation(
                "private provider exception fake-api-key"
            )

    financial_input = "buy a car with private monthly salary 987654"
    monkeypatch.setattr(
        "app.services.scenario_parser.get_ai_provider",
        lambda: UnsupportedProvider(),
    )
    response = client.post(
        "/ai/parse-scenario",
        json={"text": financial_input, "months": 12},
    )

    assert response.status_code == 200
    assert response.json()["fallback_reason"] == "unsupported_operation"
    assert "private provider exception" not in response.text
    assert "fake-api-key" not in response.text
    assert financial_input not in caplog.text
    assert "fake-api-key" not in caplog.text


def test_production_entrypoint_and_openapi_routes_remain_correct():
    import_module("app.core.demo_main")
    import_module("app.routes")

    paths = set(app.openapi()["paths"])
    expected = {
        "/ai/parse-scenario",
        "/simulate",
        "/monte-carlo",
        "/compare",
        "/ai/financial-onboarding/message",
    }
    assert app.title == "FinSim-Core API"
    assert expected <= paths
    assert "/" not in paths


def test_auth_protects_profile_route():
    response = client.get("/financial-profile")
    assert response.status_code == 401


def test_register_login_flow():
    body = {"username": "tester_api", "email": "tester_api@example.com", "password": "password123"}
    register = client.post("/auth/register", json=body)
    assert register.status_code == 200
    token = register.json()["access_token"]
    protected = client.get("/financial-profile", headers={"Authorization": f"Bearer {token}"})
    assert protected.status_code == 200
