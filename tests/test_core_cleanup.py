import json

import pytest
from fastapi.testclient import TestClient

from app.core.advisor import compare_options
from app.core.simulation import simulate_finance, summarize_simulation
from main import app


PROFILE = dict(salary=100, fixed_expense=150, variable_expense=0,
               balance=100, raise_rate=0, inflation_rate=0)


@pytest.mark.parametrize('endpoint,extra', [
    ('/simulate', {'include_details': True}),
    ('/monte-carlo', {'simulations': 3, 'include_details': True}),
    ('/compare', {'options': [{'name': 'Baseline'}], 'mc_runs': 3}),
    ('/optimize', {'max_candidates': 2}),
])
def test_api_responses_only_contain_cash_metrics(endpoint, extra):
    response = TestClient(app).post(endpoint, json={
        'profile': PROFILE, 'months': 3, 'seed': 42, **extra,
    })
    assert response.status_code == 200
    serialized = json.dumps(response.json()).lower()
    assert 'fsi' not in serialized
    assert 'bankrupt' not in serialized
    assert '破產' not in response.text
    assert 'probability_negative_balance' not in serialized
    for removed in ('risk_level', 'risk_classification', 'high_risk_months',
                    'first_risk_month', 'high_risk_month_distribution', '"score"'):
        assert removed not in serialized


def test_cash_summary_distinguishes_zero_and_negative_months():
    summary = simulate_finance(PROFILE, months=3)['summary']
    assert summary['minimum_cash_balance'] == -50
    assert summary['minimum_cash_month'] == 3
    assert summary['first_negative_cash_month'] == 3
    assert summary['minimum_emergency_fund_months'] == pytest.approx(-50 / 150, abs=.0001)
    assert simulate_finance(PROFILE, months=2)['summary']['first_negative_cash_month'] is None
    empty = summarize_simulation([], PROFILE)
    assert empty['minimum_cash_month'] is None
    assert empty['first_negative_cash_month'] is None
    assert empty['minimum_emergency_fund_months'] is None


def test_comparison_orders_by_shortfall_then_cash_median(monkeypatch):
    results = iter([
        {'probability_cash_shortfall': .2, 'median_final_balance': 1000},
        {'probability_cash_shortfall': .1, 'median_final_balance': 100},
        {'probability_cash_shortfall': .1, 'median_final_balance': 200},
    ])
    monkeypatch.setattr('app.core.advisor.run_monte_carlo', lambda **kwargs: next(results))
    comparison = compare_options(PROFILE, [{'name': name} for name in ['A', 'B', 'C']], months=1)
    assert [option['name'] for option in comparison['options']] == ['C', 'B', 'A']
    assert comparison['best_option'] == 'C'
    assert comparison['sorting_rule'] == '現金不足機率由低到高，再依期末現金中位數由高到低'


def test_cash_shortfall_counts_temporary_deficits_but_not_zero():
    from app.core.monte_carlo import run_monte_carlo

    recovered = run_monte_carlo(PROFILE, months=4, simulations=4, seed=1,
                               base_events=[{'type': 'one_time', 'month': 4, 'amount': 1000}])
    assert recovered['min_final_balance'] > 0
    assert recovered['probability_cash_shortfall'] == 1
    assert recovered['cash_shortfall_definition'] == '模擬期間任一月底現金小於 0 的試驗比例'
    zero = run_monte_carlo(PROFILE, months=2, simulations=4, seed=1)
    assert zero['probability_cash_shortfall'] == 0
    tiny_deficit = {**PROFILE, 'salary': 0, 'balance': .006, 'fixed_expense': .01}
    assert run_monte_carlo(tiny_deficit, months=1, simulations=2)['probability_cash_shortfall'] == 1


def test_optimizer_shortfall_constraint_uses_period_probability():
    from app.services.optimizer import _violations

    assert _violations({}, {'probability_cash_shortfall': .2},
                       {'cash_shortfall_probability_below': .2}) == ['Cash shortfall probability exceeds constraint']
    assert _violations({}, {'probability_cash_shortfall': 0},
                       {'cash_shortfall_probability_below': .2}) == []


def test_report_only_uses_cash_terms():
    response = TestClient(app).post('/ai/generate-report', json={
        'simulation_result': simulate_finance(PROFILE, months=3),
        'monte_carlo_result': {'probability_cash_shortfall': 1},
    })
    assert response.status_code == 200
    assert 'fsi' not in response.text.lower()
    assert 'bankrupt' not in response.text.lower()
    assert '破產' not in response.text
    assert '現金不足機率' in response.text
