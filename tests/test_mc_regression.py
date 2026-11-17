import json
from pathlib import Path
import pytest

from app.core.monte_carlo import run_monte_carlo
from app.core.simulation import simulate_finance

PROFILE = dict(salary=60000, fixed_expense=20000, variable_expense=12000, balance=900000,
               inflation_rate=.02, raise_rate=.03)
CAR = dict(name='車', start_month=6, value=800000, annual_depreciation_rate=.15)
CASES = {
    'simple': dict(profile={**PROFILE, 'variable_expense': 0}, months=60),
    'investment': dict(profile={**PROFILE, 'investment_value': 200000, 'monthly_investment': 5000}, months=60),
    'car_cash': dict(profile=PROFILE, months=60, events=[dict(type='one_time', month=6, amount=-800000)], assets=[CAR]),
    'car_loan': dict(profile=PROFILE, months=60, events=[dict(type='one_time', month=6, amount=-200000)],
                     loans=[dict(principal=600000, apr=.025, months=60, start_month=6)], assets=[CAR]),
    'existing_debts_240': dict(profile={**PROFILE, 'existing_debts': [dict(name='學貸', monthly_payment=5000, remaining_months=36)]}, months=240),
    'advanced_shocks': dict(profile={**PROFILE, 'variable_expense_model': {'mode':'advanced', 'categories': [
        dict(category='food', baseline=10000, monthly_volatility=.2, annual_inflation_rate=.03,
             income_elasticity=.7, seasonal_factors=[.8,.9,1,1.1,1.2,1,1.1,.9,1,1.2,1,.8], minimum=5000, maximum=18000),
        dict(category='transportation', baseline=3000, monthly_volatility=.1, income_elasticity=-.5,
             seasonal_factors=[1]*12, minimum=1000, maximum=8000)]}}, months=60,
        events=[dict(type='range', start_month=4, end_month=12, income_multiplier=.8,
                     target_expense_category='food', variable_expense_multiplier=1.2, category_monthly_adjustment=120)],
        random_shocks=[dict(name='維修', monthly_probability=.15, min_amount=1000, max_amount=20000,
                            distribution='uniform', duration_months=1, enabled=True)]),
}


def calculate(case):
    args = dict(case)
    events = args.pop('events', None)
    result = {'monte_carlo': run_monte_carlo(**args, base_events=events, simulations=300, seed=42),
              'simulate': simulate_finance(**args, events=events, seed=42, include_details=True)}
    if case is CASES['advanced_shocks']:
        result['monte_carlo_details'] = run_monte_carlo(**args, base_events=events, simulations=300, seed=42, include_details=True)
    return result


@pytest.mark.parametrize('name', list(CASES))
def test_mc_exact_regression(name):
    expected = json.loads((Path(__file__).parent / 'fixtures' / 'mc_baseline' / f'{name}.json').read_text(encoding='utf-8'))
    actual = calculate(CASES[name])
    for key in ("monte_carlo", "monte_carlo_details"):
        if key in actual:
            for field in ("probability_cash_shortfall_interval", "net_worth_percentile_intervals", "uncertainty_note"):
                actual[key].pop(field)
    assert actual == expected
    def check_types(a, b):
        assert type(a) is type(b)
        if isinstance(a, float):
            assert a.hex() == b.hex()
        if isinstance(a, dict):
            for key in a: check_types(a[key], b[key])
        elif isinstance(a, list):
            for left, right in zip(a, b): check_types(left, right)
    check_types(actual, expected)
