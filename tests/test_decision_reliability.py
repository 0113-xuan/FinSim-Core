import pytest

from app.core.simulation import simulate_finance
from app.core.events import calculate_loan_payment


PROFILE = dict(salary=45000, fixed_expense=15000, variable_expense=10000,
               balance=500000, raise_rate=0)


@pytest.mark.parametrize('duration', [1, 3])
def test_zero_income_multiplier(duration):
    result = simulate_finance(PROFILE, months=5, events=[dict(
        type='range', start_month=2, end_month=1 + duration, income_multiplier=0)])
    assert [r['income'] for r in result['simulation_curve'][1:1+duration]] == [0] * duration
    assert result['simulation_curve'][-1]['income'] == 45000


def test_zero_salary_change():
    result = simulate_finance(PROFILE, months=1, events=[dict(type='salary_change', start_month=1, new_salary=0)])
    assert result['simulation_curve'][0]['income'] == 0


def test_inflation_propagates():
    low = simulate_finance(PROFILE, override_inflation_rate=.01)
    high = simulate_finance(PROFILE, override_inflation_rate=.05)
    assert high['summary']['final_balance'] < low['summary']['final_balance']


def test_pmt_reference():
    payment = calculate_loan_payment(500000, .03, 60)
    assert payment == pytest.approx(8984.35, abs=.01)
    assert payment * 60 - 500000 == pytest.approx(39061, abs=1)


def test_zero_expense_multipliers():
    result = simulate_finance(PROFILE, months=1, events=[dict(type='range', start_month=1,
                              end_month=1, fixed_expense_multiplier=0, variable_expense_multiplier=0)])
    assert result['simulation_curve'][0]['expense'] == 0


def test_nominal_fixed_and_explicit_category_override():
    profile = {**PROFILE, 'variable_expense_model': {'mode': 'advanced', 'categories': [
        dict(category='food', baseline=10000, annual_inflation_rate=0)]}}
    result = simulate_finance(profile, override_inflation_rate=.05)
    assert result['simulation_curve'][-1]['fixed_expense'] == 15000
    assert result['simulation_curve'][-1]['variable_expense'] == 10000


def test_summary_and_fsi_share_debt_inclusive_coverage():
    from app.core.fsi import calculate_fsi
    result = simulate_finance(PROFILE, months=1, loans=[dict(principal=120000, apr=0, months=12, start_month=1)])
    row = result['simulation_curve'][0]
    assert result['summary']['emergency_fund_coverage'] == pytest.approx(row['balance']/35000, abs=.01)
    assert result['summary']['minimum_emergency_fund_months'] == pytest.approx(row['balance']/35000, abs=.0001)
    assert calculate_fsi(45000, 25000, 10000, 35000) == pytest.approx(.5*25000/45000+.3*10000/45000+.2*(1-1/3), abs=.0001)
