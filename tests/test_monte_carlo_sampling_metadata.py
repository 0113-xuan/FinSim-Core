import pytest
from fastapi.testclient import TestClient

from app.core.monte_carlo import run_monte_carlo
from main import app


PROFILE = dict(salary=60000, fixed_expense=20000, variable_expense=15000, balance=1000000)
SHOCK = dict(name='Repair', monthly_probability=.5, min_amount=1000, max_amount=10000,
             enabled=True)
NO_RANDOMNESS = '本次結果沒有隨機變動，分位數會相同。'
HISTORY = '2003-02 至 2026-09 共 284 個月'
PAIRED = (f'通膨率與台股報酬取自 {HISTORY}的台灣歷史月資料，每次試驗以連續 12 個月為一個區塊抽樣，'
          '同一個月的通膨與報酬成對抽取。')


def fixed(rate):
    return (f'通膨率固定使用使用者提供的 {rate}，未抽樣；台股報酬取自 {HISTORY}的歷史月資料，以連續 12 個月為一個區塊抽樣。'
            '歷史通膨與報酬按同一個月份成對選取，但通膨以使用者的固定值取代。')


TAIL = '預期年報酬率（expected_annual_return）只用於確定性模擬，不影響 Monte Carlo。歷史期間台股表現特別好，過去報酬不代表未來。'


@pytest.mark.parametrize('rates,shocks,parameters,note', [
    ({}, [], ['inflation_rate', 'raise_rate'], PAIRED + '調薪率跟隨該次試驗的實際通膨，每年調整一次。' + TAIL),
    ({'raise_rate': 0}, [], ['inflation_rate'], PAIRED + '調薪率固定使用使用者提供的 0%。' + TAIL),
    ({'inflation_rate': .02}, [SHOCK], [], fixed('2%') + '調薪率等於固定通膨率。' + TAIL),
    ({'inflation_rate': .02}, [], [], fixed('2%') + '調薪率等於固定通膨率。' + TAIL + NO_RANDOMNESS),
    ({'inflation_rate': 0, 'raise_rate': .035}, [], [],
     fixed('0%') + '調薪率固定使用使用者提供的 3.5%。' + TAIL + NO_RANDOMNESS),
    ({'inflation_rate': .02}, [{**SHOCK, 'enabled': False}], [],
     fixed('2%') + '調薪率等於固定通膨率。' + TAIL + NO_RANDOMNESS),
    ({'inflation_rate': .02, 'investment_value': 100000}, [], ['investment_return'],
     fixed('2%') + '調薪率等於固定通膨率。投資市值依抽樣的台股報酬指數（含股利再投入）變動，現金不足時也不會自動賣出。' + TAIL),
])
def test_sampling_metadata_matches_effective_api_inputs(rates, shocks, parameters, note):
    response = TestClient(app).post('/monte-carlo', json={
        'profile': {**PROFILE, **rates}, 'random_shocks': shocks,
        'months': 60, 'simulations': 20, 'seed': 42,
    })
    assert response.status_code == 200
    result = response.json()
    expected_parameters = parameters if 'investment_return' in parameters else parameters + ['investment_return']
    assert result['sampled_parameters'] == expected_parameters
    if not rates.get('investment_value'):
        note = note.replace(TAIL, '未設定投資市值或每月投入，抽樣報酬不影響帳戶金額。' + TAIL)
    assert result['sampling_note'] == note
    assert result['sampling_method']['block_months'] == 12
    if NO_RANDOMNESS in note:
        assert len(set(result['percentiles'].values())) == 1
    elif 'investment_return' in parameters:
        assert result['net_worth_percentiles']['p95'] > result['net_worth_percentiles']['p5']
    else:
        assert result['percentiles']['p95'] > result['percentiles']['p5']


def test_advanced_expense_volatility_is_not_described_as_deterministic():
    profile = {**PROFILE, 'inflation_rate': .02, 'variable_expense_model': {
        'mode': 'advanced', 'categories': [
            {'category': 'food', 'baseline': 15000, 'monthly_volatility': .2},
            {'category': 'shopping', 'baseline': 1000, 'monthly_volatility': .3, 'enabled': False},
        ],
    }}
    result = run_monte_carlo(profile, months=24, simulations=20, seed=42)
    assert result['sampled_parameters'] == ['investment_return', 'variable_expense']
    assert '變動支出依已啟用分類的月波動率抽樣。' in result['sampling_note']
    assert NO_RANDOMNESS not in result['sampling_note']
    assert result['percentiles']['p95'] > result['percentiles']['p5']


@pytest.mark.parametrize('mode,enabled,expected_note', [
    ('advanced', True, True),
    ('advanced', None, True),  # An omitted enabled flag defaults to enabled.
    ('advanced', False, False),
    ('quick', True, False),
])
def test_sampling_note_explains_only_active_advanced_categories(mode, enabled, expected_note):
    category = dict(category='food', baseline=10000, annual_inflation_rate=0, monthly_volatility=0)
    if isinstance(enabled, bool):
        category['enabled'] = enabled
    response = TestClient(app).post('/monte-carlo', json={
        'profile': {**PROFILE, 'variable_expense_model': {'mode': mode, 'categories': [category]}},
        'months': 25, 'simulations': 3, 'sample_paths': 3, 'include_details': True, 'seed': 42,
    })
    assert response.status_code == 200
    result = response.json()
    note = '進階模式的支出分類使用各自設定的通膨率，不跟隨抽樣通膨。'
    assert (note in result['sampling_note']) is expected_note
    if expected_note:
        for path in result['debug_paths']:
            assert all(row['variable_expense'] == 10000 for row in path['simulation_curve'])
