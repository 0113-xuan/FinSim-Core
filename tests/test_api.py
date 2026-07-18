from fastapi.testclient import TestClient

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
    assert food["source"] == "AI 推估"
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
