import pytest
from fastapi.testclient import TestClient

from app.core.monte_carlo import run_monte_carlo
from main import app


PROFILE = dict(salary=60000, fixed_expense=20000, variable_expense=15000, balance=1000000)
SHOCK = dict(name='Repair', monthly_probability=.5, min_amount=1000, max_amount=10000,
             enabled=True)
NO_RANDOMNESS = '本次結果沒有隨機變動，分位數會相同。'


@pytest.mark.parametrize('rates,shocks,parameters,note', [
    ({}, [], ['inflation_rate', 'raise_rate'],
     '通膨率暫以 1%–5% 均勻抽樣，範圍為暫時設定，沒有資料來源。調薪率等於該次試驗的通膨率。'),
    ({'raise_rate': 0}, [], ['inflation_rate'],
     '通膨率暫以 1%–5% 均勻抽樣，範圍為暫時設定，沒有資料來源。調薪率固定使用 0%。'),
    ({'inflation_rate': .02}, [SHOCK], [],
     '通膨率固定使用 2%，未抽樣。調薪率等於該次試驗的通膨率。'),
    ({'inflation_rate': .02}, [], [],
     '通膨率固定使用 2%，未抽樣。調薪率等於該次試驗的通膨率。' + NO_RANDOMNESS),
    ({'inflation_rate': 0, 'raise_rate': .035}, [], [],
     '通膨率固定使用 0%，未抽樣。調薪率固定使用 3.5%。' + NO_RANDOMNESS),
    ({'inflation_rate': .02}, [{**SHOCK, 'enabled': False}], [],
     '通膨率固定使用 2%，未抽樣。調薪率等於該次試驗的通膨率。' + NO_RANDOMNESS),
])
def test_sampling_metadata_matches_effective_api_inputs(rates, shocks, parameters, note):
    response = TestClient(app).post('/monte-carlo', json={
        'profile': {**PROFILE, **rates}, 'random_shocks': shocks,
        'months': 60, 'simulations': 20, 'seed': 42,
    })
    assert response.status_code == 200
    result = response.json()
    assert result['sampled_parameters'] == parameters
    assert result['sampling_note'] == note
    if NO_RANDOMNESS in note:
        assert len(set(result['percentiles'].values())) == 1
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
    assert result['sampled_parameters'] == ['variable_expense']
    assert '變動支出依已啟用分類的月波動率抽樣。' in result['sampling_note']
    assert NO_RANDOMNESS not in result['sampling_note']
    assert result['percentiles']['p95'] > result['percentiles']['p5']
