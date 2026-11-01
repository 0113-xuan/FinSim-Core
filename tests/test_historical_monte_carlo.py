import math

import pytest
from fastapi.testclient import TestClient

from app.core.market_data import load_market_history
from app.core.monte_carlo import PAST_PERFORMANCE_WARNING, run_monte_carlo
from app.core.simulation import simulate_finance
from main import app


HISTORY = load_market_history()
PROFILE = dict(salary=60000, fixed_expense=20000, variable_expense=15000, balance=500000)


def _matching_starts(inflation, returns):
    """History months whose consecutive inflation and return pairs equal the sampled block."""
    size = len(inflation)
    return [start for start in range(len(HISTORY.periods) - size + 1)
            if list(HISTORY.inflation[start:start + size]) == inflation
            and list(HISTORY.returns[start:start + size]) == returns]


def test_seeded_monte_carlo_is_reproducible():
    profile = {**PROFILE, 'investment_value': 100000, 'monthly_investment': 5000}
    first = run_monte_carlo(profile, months=36, simulations=30, seed=7, include_details=True)
    assert first == run_monte_carlo(profile, months=36, simulations=30, seed=7, include_details=True)
    assert first != run_monte_carlo(profile, months=36, simulations=30, seed=8, include_details=True)


def test_blocks_are_consecutive_months_with_paired_inflation_and_returns():
    result = run_monte_carlo(PROFILE, months=30, simulations=3, sample_paths=3, seed=11, include_details=True)
    for path in result['debug_paths']:
        assert len(path['inflation_path']) == len(path['return_path']) == 30
        for start in range(0, 30, 12):
            block = slice(start, start + 12)
            starts = _matching_starts(path['inflation_path'][block], path['return_path'][block])
            # A block is one run of consecutive history months, never wrapped past the end.
            assert starts and all(index <= len(HISTORY.periods) - 12 for index in starts)


def test_investment_account_matches_hand_calculation():
    profile = {**PROFILE, 'investment_value': 100000, 'monthly_investment': 1000}
    curve = simulate_finance(profile, months=12, return_path=[0.01] * 12)['simulation_curve']
    # Month 1: 100,000 × 1.01 + 1,000 = 102,000
    assert curve[0]['investment_value'] == 102000
    # Month 2: 102,000 × 1.01 + 1,000 = 104,020
    assert curve[1]['investment_value'] == 104020
    # Month 12: 100,000 × 1.01^12 + 1,000 × (1.01^12 − 1) / 0.01
    #         = 112,682.503 + 12,682.503 = 125,365.01
    assert curve[11]['investment_value'] == 125365.01
    assert curve[11]['net_worth'] == round(curve[11]['balance'] + curve[11]['investment_value'], 2)


def test_deterministic_return_uses_expected_annual_return_or_history():
    profile = {**PROFILE, 'investment_value': 100000}
    explicit = simulate_finance({**profile, 'expected_annual_return': .05}, months=12)
    assert explicit['summary']['final_investment_value'] == pytest.approx(105000, abs=.01)
    historical = simulate_finance(profile, months=12)
    assert historical['summary']['final_investment_value'] == pytest.approx(100000 * (1 + HISTORY.annual_return_rate), abs=.01)


def test_negative_cash_never_sells_investments():
    profile = dict(salary=0, fixed_expense=30000, variable_expense=0, balance=10000,
                   investment_value=200000, monthly_investment=5000)
    returns = [0.02, -0.03] * 12
    curve = simulate_finance(profile, months=24, return_path=returns)['simulation_curve']
    assert curve[-1]['balance'] < 0
    expected = 200000.0
    for row, rate in zip(curve, returns):
        expected = expected * (1 + rate) + 5000
        assert row['investment_value'] == round(expected, 2)
    assert curve[0]['balance'] == 10000 - 30000 - 5000


def test_monthly_investment_is_not_living_expense():
    base = simulate_finance(PROFILE, months=24, override_inflation_rate=.02)['simulation_curve']
    investing = simulate_finance({**PROFILE, 'monthly_investment': 20000}, months=24,
                                 override_inflation_rate=.02)['simulation_curve']
    assert [row['living_expense'] for row in investing] == [row['living_expense'] for row in base]
    assert investing[-1]['balance'] == pytest.approx(base[-1]['balance'] - 24 * 20000, abs=.01)


def test_default_salary_follows_sampled_inflation():
    result = run_monte_carlo({**PROFILE, 'fixed_expense_inflates': True}, months=13, simulations=3,
                             sample_paths=3, seed=5, include_details=True)
    for path in result['debug_paths']:
        prices = math.prod(1 + rate for rate in path['inflation_path'][:12])
        assert path['simulation_curve'][11]['income'] == 60000
        assert path['simulation_curve'][12]['income'] == round(60000 * prices, 2)
        assert path['simulation_curve'][12]['fixed_expense'] == round(20000 * prices, 2)


def test_salary_change_follows_inflation_since_the_change():
    events = [dict(type='salary_change', start_month=3, new_salary=70000)]
    path = [0.001 * (index % 5) for index in range(30)]
    curve = simulate_finance(PROFILE, months=30, events=events, inflation_path=path,
                             return_path=[0.0] * 30)['simulation_curve']
    assert curve[13]['income'] == 70000
    assert curve[14]['income'] == round(70000 * math.prod(1 + rate for rate in path[2:14]), 2)


def test_fixed_inflation_keeps_prices_but_returns_still_vary():
    profile = {**PROFILE, 'inflation_rate': .02, 'investment_value': 300000}
    result = run_monte_carlo(profile, months=36, simulations=40, sample_paths=3, seed=3, include_details=True)
    assert {path['price_multiplier'] for path in result['debug_paths']} == {1.02 ** 3}
    assert len({path['simulation_curve'][-1]['variable_expense'] for path in result['debug_paths']}) == 1
    assert len({path['summary']['final_net_worth'] for path in result['debug_paths']}) > 1
    assert result['net_worth_percentiles']['p95'] > result['net_worth_percentiles']['p5']
    assert result['sampled_parameters'] == ['investment_return']
    assert result['fixed_parameters'] == ['inflation_rate']
    # Deflating by one common price multiplier preserves the order of trials.
    for key in ('p5', 'p50', 'p95'):
        assert result['real_net_worth_percentiles'][key] == pytest.approx(
            result['net_worth_percentiles'][key] / 1.02 ** 3, abs=.02)


def test_deterministic_cash_matches_historical_inflation_hand_calculation():
    profile = dict(salary=50000, fixed_expense=20000, variable_expense=0, balance=100000,
                   fixed_expense_inflates=True)
    rate = HISTORY.annual_inflation_rate
    result = simulate_finance(profile, months=24)
    # Year 1: 12 × (50,000 − 20,000); year 2: both amounts grow by one year of historical inflation.
    expected = 100000 + 12 * 30000 + 12 * (round(50000 * (1 + rate), 2) - round(20000 * (1 + rate), 2))
    assert result['summary']['final_balance'] == round(expected, 2)
    assert result['summary']['final_net_worth'] == result['summary']['final_balance']
    assert result['summary']['final_investment_value'] == 0
    response = TestClient(app).post('/simulate', json={'profile': profile, 'months': 24})
    assert response.status_code == 200
    assert response.json()['result']['summary']['final_balance'] == round(expected, 2)


@pytest.mark.parametrize('category_rate', [0, .03])
def test_advanced_categories_keep_their_own_inflation_rate(category_rate):
    profile = {**PROFILE, 'variable_expense_model': {'mode': 'advanced', 'categories': [
        dict(category='food', baseline=10000, annual_inflation_rate=category_rate, monthly_volatility=0)]}}
    inflation = [0.01] * 12 + [-0.005] * 12 + [0] * 12
    sampled = simulate_finance(profile, months=25, inflation_path=inflation)['simulation_curve']
    assert [row['variable_expense'] for row in sampled] == [
        round(10000 * (1 + category_rate) ** ((month - 1) // 12), 2) for month in range(1, 26)]
    fixed = simulate_finance({**profile, 'inflation_rate': .04}, months=13)['simulation_curve']
    assert fixed[12]['variable_expense'] == round(10000 * (1 + category_rate), 2)


def test_expected_annual_return_does_not_change_monte_carlo():
    profile = {**PROFILE, 'investment_value': 100000}
    low = run_monte_carlo({**profile, 'expected_annual_return': -.4}, months=24, simulations=10, seed=3)
    high = run_monte_carlo({**profile, 'expected_annual_return': .8}, months=24, simulations=10, seed=3)
    assert low == high


def test_monte_carlo_response_reports_net_worth_and_sources():
    response = TestClient(app).post('/monte-carlo', json={
        'profile': {**PROFILE, 'investment_value': 100000, 'monthly_investment': 3000},
        'months': 60, 'simulations': 50, 'seed': 42,
    })
    assert response.status_code == 200
    result = response.json()
    assert list(result['net_worth_percentiles']) == ['p5', 'p25', 'p50', 'p75', 'p95']
    assert list(result['real_net_worth_percentiles']) == ['p5', 'p50', 'p95']
    assert result['real_net_worth_percentiles']['p50'] < result['net_worth_percentiles']['p50']
    assert PAST_PERFORMANCE_WARNING in result['sampling_note']
    assert [source['publisher'] for source in result['data_sources']] == ['行政院主計總處', '臺灣證券交易所']
    for source in result['data_sources']:
        assert set(source) == {'name', 'publisher', 'url', 'period_start', 'period_end', 'downloaded'}


def test_profile_rejects_negative_investment_inputs():
    for field in ('investment_value', 'monthly_investment'):
        response = TestClient(app).post('/simulate', json={'profile': {**PROFILE, field: -1}})
        assert response.status_code == 422
