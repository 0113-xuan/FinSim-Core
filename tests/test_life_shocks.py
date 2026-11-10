from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.simulation import simulate_finance
from main import app

PROFILE = dict(salary=60000, fixed_expense=20000, balance=100000, inflation_rate=0, raise_rate=0,
               variable_expense_model=dict(mode='advanced', categories=[dict(category='food', baseline=10000,
                   annual_inflation_rate=0, monthly_volatility=.2, income_elasticity=-1)]))
GAP = dict(name='收入中斷', monthly_probability=1, min_amount=0, max_amount=0, duration_months=2,
           income_multiplier=0)
BODY = dict(profile=PROFILE, months=60, simulations=30, seed=42, sample_paths=0)
CLIENT = TestClient(app)


def test_income_gap_duration_overlap_and_details():
    # Triggers in months 1 and 2; each ends independently, with the smaller multiplier winning.
    draws = iter([dict(total=0, details=[dict(name='gap')], income_shocks=[(.5, 3)]),
                  dict(total=0, details=[dict(name='gap')], income_shocks=[(0, 2)])] +
                 [dict(total=0, details=[], income_shocks=[])] * 2)
    with patch('app.core.simulation.generate_shocks_for_month', side_effect=lambda **_: next(draws)):
        result = simulate_finance(PROFILE, months=4, seed=42, include_details=True)
    assert [row['income'] for row in result['simulation_curve']] == [30000, 0, 0, 60000]
    assert len(result['shock_details']) == 2
    actual = simulate_finance(PROFILE, months=2, random_shocks=[GAP], seed=42, include_details=True)
    baseline = simulate_finance(PROFILE, months=2, seed=42)
    assert actual['shock_details'][0]['income_multiplier'] == 0
    assert [r['variable_expense'] for r in actual['simulation_curve']] == [r['variable_expense'] for r in baseline['simulation_curve']]
    assert all(r['income'] == 0 for r in actual['simulation_curve'])


def test_independent_randomness_and_seed_none():
    shock = dict(name='repair', monthly_probability=.5, min_amount=1000, max_amount=5000)
    baseline = simulate_finance(PROFILE, months=30, seed=123)
    first = simulate_finance(PROFILE, months=30, seed=123, random_shocks=[shock])
    second = simulate_finance(PROFILE, months=30, seed=123, random_shocks=[shock])
    assert first['simulation_curve'] == second['simulation_curve']
    assert [r['variable_expense'] for r in first['simulation_curve']] == [r['variable_expense'] for r in baseline['simulation_curve']]
    assert simulate_finance(PROFILE, months=2, seed=None, random_shocks=[shock])


def test_endpoint_comparison_reproducibility_and_assumptions():
    baseline = CLIENT.post('/monte-carlo', json=BODY)
    first = CLIENT.post('/monte-carlo/life-shocks', json=BODY)
    second = CLIENT.post('/monte-carlo/life-shocks', json=BODY)
    assert baseline.status_code == first.status_code == second.status_code == 200
    data = first.json()
    assert data == second.json()
    assert data['probability_cash_shortfall'] >= baseline.json()['probability_cash_shortfall']
    assert [x['id'] for x in data['assumptions']] == ['medical', 'accident', 'income_gap']
    for item in data['assumptions']:
        assert item['chance_in_horizon'] == round(1 - (1 - item['monthly_probability']) ** BODY['months'], 4)
    assert data['assumptions'][0]['chance_in_horizon'] == 0.2597
    rejected = CLIENT.post('/monte-carlo/life-shocks', json={**BODY, 'random_shocks': [GAP]})
    assert rejected.status_code == 422
    assert rejected.json()['detail'] == '此端點會自行帶入意外情境，請不要傳 random_shocks'


@pytest.mark.parametrize('multiplier', [-.01, 1.01])
def test_multiplier_validation(multiplier):
    response = CLIENT.post('/simulate', json={**BODY, 'random_shocks': [{**GAP, 'income_multiplier': multiplier}]})
    assert response.status_code == 422
