from app.core.events import calculate_loan_payment
from app.core.fsi import calculate_fsi, classify_risk
from app.core.monte_carlo import run_monte_carlo
from app.core.simulation import simulate_finance
from app.schemas import ParsedScenario
from app.services.expense_categorizer import categorize_expenses
from app.services.optimizer import optimize
from app.services.scenario_parser import deterministic_parse_scenario
from app.schemas import CategorizeExpensesRequest, ScenarioParseRequest


def profile():
    return {
        "salary": 60000,
        "fixed_expense": 20000,
        "variable_expense": 15000,
        "balance": 1000000,
        "raise_rate": 0.03,
        "inflation_rate": 0.02,
        "target_emergency_months": 6,
        "variable_expense_model": {
            "mode": "quick",
            "total_variable_expense": 15000,
            "categories": [],
        },
    }


def test_fsi_and_risk_classification():
    fsi = calculate_fsi(income=60000, expense=35000, debt_payment=0, balance=500000, target_emergency_months=6)
    assert fsi < 0.6
    assert classify_risk(fsi, 500000) in {"low", "medium"}
    assert classify_risk(fsi, -1) == "crisis"


def test_loan_payment():
    payment = calculate_loan_payment(600000, 0.03, 60)
    assert 10000 < payment < 12000


def test_basic_simulation_uses_categories_and_events():
    advanced = profile()
    advanced["variable_expense_model"] = {
        "mode": "advanced",
        "total_variable_expense": 15000,
        "categories": [
            {
                "category": "food",
                "baseline": 10000,
                "monthly_volatility": 0,
                "annual_inflation_rate": 0.12,
                "income_elasticity": 0,
                "seasonal_factors": [1] * 12,
                "enabled": True,
            }
        ],
    }
    result = simulate_finance(
        advanced,
        months=13,
        events=[{"type": "life_event", "name": "Child", "start_month": 2, "monthly_amount": -1000, "target_expense_category": "food"}],
        seed=1,
        include_details=True,
    )
    assert result["simulation_curve"][0]["variable_expense"] == 10000
    assert result["simulation_curve"][12]["variable_expense"] > 10000
    assert "expense_categories" in result["simulation_curve"][0]


def test_category_adjustment_and_recurring_cashflow_are_not_double_counted():
    advanced = profile()
    advanced["fixed_expense"] = 0
    advanced["variable_expense_model"] = {
        "mode": "advanced",
        "total_variable_expense": 1000,
        "categories": [
            {
                "category": "food",
                "baseline": 1000,
                "monthly_volatility": 0,
                "annual_inflation_rate": 0,
                "income_elasticity": 0,
                "seasonal_factors": [1] * 12,
                "enabled": True,
            }
        ],
    }
    result = simulate_finance(
        advanced,
        months=1,
        events=[
            {
                "type": "life_event",
                "name": "Travel food",
                "start_month": 1,
                "category_monthly_adjustment": 500,
                "target_expense_category": "food",
            },
            {
                "type": "life_event",
                "name": "Loan",
                "start_month": 1,
                "monthly_amount": -500,
            },
        ],
        include_details=True,
    )
    row = result["simulation_curve"][0]
    assert row["variable_expense"] == 1500
    assert row["event_net"] == -500
    assert row["net_cashflow"] == 58000


def test_random_shock_seed_reproducibility():
    shocks = [{"name": "Repair", "monthly_probability": 1, "min_amount": 1000, "max_amount": 1000, "duration_months": 1, "distribution": "uniform", "enabled": True}]
    a = simulate_finance(profile(), months=3, random_shocks=shocks, seed=7)
    b = simulate_finance(profile(), months=3, random_shocks=shocks, seed=7)
    assert a["simulation_curve"] == b["simulation_curve"]


def test_monte_carlo_outputs_percentiles_and_seed():
    result = run_monte_carlo(profile(), months=12, simulations=20, seed=123, sample_paths=2)
    assert result["seed"] == 123
    assert "p5" in result["percentiles"]
    assert len(result["sample_paths"]) == 2


def test_ai_fallback_validation_and_categorization():
    parsed = deterministic_parse_scenario(ScenarioParseRequest(text="move to Taipei and travel to Japan", months=60))
    assert isinstance(parsed, ParsedScenario)
    assert parsed.events
    chinese = deterministic_parse_scenario(ScenarioParseRequest(text="半年後搬家，每月房租增加 8000 元", months=60))
    assert chinese.clarification.intent == "relocation"
    assert "one_time_costs" in chinese.clarification.missing_fields
    assert "30000" not in str(chinese.model_dump())
    unclear = deterministic_parse_scenario(ScenarioParseRequest(text="今天天氣真好", months=60))
    assert not unclear.events
    assert not unclear.expense_adjustments
    assert unclear.confidence < 0.3
    categorized = categorize_expenses(CategorizeExpensesRequest(total_variable_expense=20000))
    assert round(sum(item.amount for item in categorized.categories), 2) == 20000


def test_optimization_constraints():
    result = optimize({"profile": profile(), "months": 12, "seed": 1, "constraints": {"maximum_fsi_below": 0.9}, "max_candidates": 5})
    assert "best_scenario" in result
    assert "rejected_scenarios" in result
