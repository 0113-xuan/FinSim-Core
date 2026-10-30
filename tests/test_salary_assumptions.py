import pytest
from fastapi.testclient import TestClient

from app.core.monte_carlo import run_monte_carlo
from app.core.simulation import simulate_finance
from main import app


PROFILE = dict(salary=1000, fixed_expense=100, variable_expense=0, balance=0)


@pytest.mark.parametrize('inflation', [0, .04, -.02])
def test_deterministic_default_salary_follows_effective_inflation(inflation):
    response = TestClient(app).post('/simulate', json={
        'profile': {**PROFILE, 'inflation_rate': inflation}, 'months': 13,
    })
    assert response.status_code == 200
    result = response.json()['result']
    assert result['simulation_curve'][12]['income'] == round(1000 * (1 + inflation), 2)
    assumption = next(a for a in result['transparency']['assumptions'] if a['label'] == '年調薪率')
    assert assumption['value'] == inflation
    assert assumption['source'] == '系統模擬假設'


@pytest.mark.parametrize('raise_rate', [0, .08, -.1])
def test_explicit_salary_rate_wins_in_deterministic_simulation(raise_rate):
    result = simulate_finance({**PROFILE, 'raise_rate': raise_rate, 'inflation_rate': .04}, months=13)
    assert result['simulation_curve'][12]['income'] == round(1000 * (1 + raise_rate), 2)


def test_default_salary_follows_inflation_override():
    result = simulate_finance(PROFILE, months=13, override_inflation_rate=.06)
    assert result['simulation_curve'][12]['income'] == 1060


@pytest.mark.parametrize('rates', [{}, {'raise_rate': None}, {'raise_rate': 0},
                                  {'inflation_rate': 0}, {'inflation_rate': .12},
                                  {'raise_rate': .08, 'inflation_rate': .12},
                                  {'raise_rate': 0, 'inflation_rate': 0}])
def test_monte_carlo_respects_explicit_rates_and_links_omitted_salary(rates):
    response = TestClient(app).post('/monte-carlo', json={
        'profile': {**PROFILE, 'variable_expense': 100, **rates},
        'months': 13, 'simulations': 3, 'sample_paths': 3, 'seed': 42, 'include_details': True,
    })
    assert response.status_code == 200
    result = response.json()
    assert '暫時設定' in result['sampling_note'] and '沒有資料來源' in result['sampling_note']
    for path in result['debug_paths']:
        row = path['simulation_curve'][12]
        income = row['income']
        if 'inflation_rate' in rates:
            assert row['variable_expense'] == pytest.approx(100 * (1 + rates['inflation_rate']), abs=.06)
        else:
            assert 101 <= row['variable_expense'] <= 105
        if rates.get('raise_rate') is not None:
            assert income == round(1000 * (1 + rates['raise_rate']), 2)
        elif 'inflation_rate' in rates:
            assert income == round(1000 * (1 + rates['inflation_rate']), 2)
        else:
            assert 1010 <= income <= 1050
            assert income == pytest.approx(row['variable_expense'] * 10, abs=.6)


def test_sampled_salary_and_inflation_match_each_trial():
    profile = {**PROFILE, 'fixed_expense_inflates': True}
    result = run_monte_carlo(profile, months=13, simulations=3, sample_paths=3,
                            seed=42, include_details=True)
    annual_incomes = []
    for path in result['debug_paths']:
        row = path['simulation_curve'][12]
        assert row['income'] == pytest.approx(row['fixed_expense'] * 10, abs=.06)
        annual_incomes.append(row['income'])
    assert len(set(annual_incomes)) > 1
    assert result == run_monte_carlo(profile, months=13, simulations=3, sample_paths=3,
                                    seed=42, include_details=True)


@pytest.mark.parametrize('endpoint,extra', [
    ('/compare', {'options': [{'name': 'Baseline'}], 'mc_runs': 3}),
    ('/optimize', {'max_candidates': 1}),
])
def test_comparison_and_optimization_preserve_rate_omission(endpoint, extra):
    response = TestClient(app).post(endpoint, json={
        'profile': PROFILE, 'months': 13, 'seed': 42, **extra,
    })
    assert response.status_code == 200
    data = response.json()
    option = data['compare_result']['options'][0] if endpoint == '/compare' else data['baseline']
    assert option['simulation_summary']['final_balance'] == 11720
    paths = option['monte_carlo_summary']['sample_paths']
    assert len({path['points'][-1]['balance'] for path in paths}) > 1


def test_option_rate_overrides_work_when_base_rate_is_omitted():
    response = TestClient(app).post('/compare', json={
        'profile': PROFILE, 'months': 13, 'mc_runs': 3, 'seed': 42,
        'options': [{'name': 'Override', 'profile_overrides': {'inflation_rate': .1}}],
    })
    assert response.status_code == 200
    option = response.json()['compare_result']['options'][0]
    assert option['simulation_summary']['final_balance'] == 11800
    assert option['monte_carlo_summary']['median_final_balance'] == 11800
