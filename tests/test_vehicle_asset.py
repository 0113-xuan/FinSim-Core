import pytest
from fastapi.testclient import TestClient

from app.core.balance_sheet import asset_value, existing_debt_balance, loan_balance
from app.core.monte_carlo import run_monte_carlo
from app.core.simulation import simulate_finance
from app.services.vehicle_decision import NON_CASH_ROW_FIELDS
from main import app


CLIENT = TestClient(app)
PROFILE = dict(salary=60000, fixed_expense=20000, variable_expense=10000, balance=900000,
               inflation_rate=.02, raise_rate=0)
NEW_FIELDS = ('asset_value', 'loan_balance', 'existing_debt_balance')


def convert(details, purchase='2027-09', months=60):
    response = CLIENT.post('/planner/vehicle-events', json=dict(
        start_period='2026-11', months=months, inflation_rate=.02,
        vehicles=[dict(name='買車', purchase_period=purchase, details=details)]))
    assert response.status_code == 200, response.json()
    return response.json()


def simulate(**request):
    response = CLIENT.post('/simulate', json=dict(profile=PROFILE, months=60, **request))
    assert response.status_code == 200, response.json()
    return response.json()['result']['simulation_curve']


def test_depreciation_matches_hand_calculation():
    asset = dict(start_month=5, value=800000, annual_depreciation_rate=.15)
    assert asset_value(asset, 4) == 0
    # Purchase month: held 0 months → 800,000
    assert asset_value(asset, 5) == 800000
    # Held 12 months: 800,000 × 0.85 = 680,000
    assert asset_value(asset, 17) == pytest.approx(680000)
    # Held 24 months: 800,000 × 0.85² = 578,000
    assert asset_value(asset, 29) == pytest.approx(578000)
    curve = simulate_finance(PROFILE, months=29, assets=[{**asset, 'name': '車'}])['simulation_curve']
    assert [curve[i]['asset_value'] for i in (3, 4, 16, 28)] == [0, 800000, 680000, 578000]


def test_loan_balance_matches_amortization():
    loan = dict(principal=600000, apr=.025, months=60, start_month=3)
    assert loan_balance(loan, 2) == 0
    # Payment = PMT(600,000, 2.5%/12, 60) = 10,648.42
    # Month 1: 600,000 × (1 + 0.025/12) − 10,648.42 = 590,601.58
    assert loan_balance(loan, 3) == pytest.approx(590601.58, abs=.01)
    # Month 2: 590,601.58 × (1 + 0.025/12) − 10,648.42 = 581,183.58
    assert loan_balance(loan, 4) == pytest.approx(581183.58, abs=.01)
    # Payments run in months 3–62. After the 59th payment (month 61) 10,626.09 remains.
    assert loan_balance(loan, 61) == pytest.approx(10626.09, abs=.01)
    # After the 60th payment nothing is owed; rounding cents are absorbed by the last payment.
    assert loan_balance(loan, 62) == 0
    assert loan_balance(loan, 63) == 0


@pytest.mark.parametrize('details,interest', [
    (dict(purchase_price=809000, payment_method='cash'), False),
    (dict(purchase_price=809000, payment_method='financed', down_payment=200000,
          loan_term_months=60, annual_interest_rate=.025), True),
])
def test_purchase_month_net_worth_only_loses_costs_not_the_car(details, interest):
    converted = convert(details)
    month = converted['vehicles'][0]['purchase_month']
    base = simulate()
    car = simulate(events=converted['events'], loans=converted['loans'], assets=converted['assets'])
    ownership = converted['vehicles'][0]['first_year_monthly_ownership_cost']
    # The first loan payment falls in the purchase month: 609,000 × 2.5% / 12 of it is interest.
    first_interest = 609000 * .025 / 12 if interest else 0
    before = car[month - 2]['net_worth'] - base[month - 2]['net_worth']
    after = car[month - 1]['net_worth'] - base[month - 1]['net_worth']
    assert before == 0
    assert after == pytest.approx(-(ownership + first_interest), abs=.02)
    assert car[month - 1]['asset_value'] == 809000
    expected_loan = 609000 - (10808.14 - first_interest) if interest else 0
    assert car[month - 1]['loan_balance'] == pytest.approx(expected_loan, abs=.02)


def test_existing_debts_reduce_net_worth_without_double_payment():
    debts = [dict(name='學貸', monthly_payment=5000, remaining_months=24)]
    curve = simulate_finance({**PROFILE, 'existing_debts': debts}, months=30)['simulation_curve']
    # 5,000 × (24 − 1) = 115,000 still owed after month 1.
    assert curve[0]['existing_debt_balance'] == 115000
    assert curve[23]['existing_debt_balance'] == 0
    assert curve[29]['existing_debt_balance'] == 0
    assert existing_debt_balance(debts, 1) == 115000
    as_events = simulate_finance(PROFILE, months=30, events=[dict(
        type='range', name='學貸', start_month=1, end_month=24, monthly_amount=-5000)])['simulation_curve']
    assert [row['balance'] for row in curve] == [row['balance'] for row in as_events]
    assert curve[0]['net_worth'] == curve[0]['balance'] - 115000


def test_api_accepts_existing_debts_and_assets_and_reports_final_balances():
    response = CLIENT.post('/simulate', json=dict(
        profile={**PROFILE, 'existing_debts': [dict(name='學貸', monthly_payment=5000, remaining_months=100)]},
        months=12, assets=[dict(name='車', start_month=1, value=100000, annual_depreciation_rate=.1)]))
    summary = response.json()['result']['summary']
    assert summary['final_existing_debt_balance'] == 5000 * 88
    assert summary['final_asset_value'] == pytest.approx(100000 * .9 ** (11 / 12), abs=.01)
    assert summary['final_loan_balance'] == 0
    bad = CLIENT.post('/simulate', json=dict(profile=PROFILE, assets=[
        dict(name='車', start_month=1, value=100000, annual_depreciation_rate=-.1)]))
    assert bad.status_code == 422


def test_profiles_without_assets_or_liabilities_keep_cash_only_net_worth():
    curve = simulate_finance({**PROFILE, 'investment_value': 100000, 'monthly_investment': 1000}, months=24)['simulation_curve']
    for row in curve:
        assert all(row[field] == 0 for field in NEW_FIELDS)
        assert row['net_worth'] == round(row['balance'] + row['investment_value'], 2)


def test_vehicle_decision_timeline_stays_cash_only():
    assert set(NON_CASH_ROW_FIELDS) >= {'investment_value', 'net_worth', *NEW_FIELDS}


def test_planner_vehicle_reports_economic_cost():
    details = dict(purchase_price=809000, payment_method='financed', down_payment=200000,
                   loan_term_months=60, annual_interest_rate=.025, annual_depreciation_rate=.2)
    car = convert(details)['vehicles'][0]
    held = 60 - car['purchase_month']
    assert 'annual_depreciation_rate' not in car['defaults_used']
    assert car['ending_vehicle_value'] == pytest.approx(809000 * .8 ** (held / 12), abs=.01)
    assert car['depreciation_in_horizon'] == pytest.approx(809000 - car['ending_vehicle_value'], abs=.01)
    assert car['economic_cost_in_horizon'] == pytest.approx(
        car['depreciation_in_horizon'] + car['interest_in_horizon'] + car['ownership_cost_in_horizon'], abs=.02)
    # 50 of 60 payments fall inside the horizon, so less than the full-term interest.
    assert 0 < car['interest_in_horizon'] < car['total_loan_interest']


def test_monte_carlo_values_vehicles_identically_and_includes_them_in_net_worth():
    assets = [dict(name='車', start_month=3, value=800000, annual_depreciation_rate=.15)]
    result = run_monte_carlo({**PROFILE, 'investment_value': 100000}, months=36, simulations=20,
                             sample_paths=3, seed=4, include_details=True, assets=assets)
    values = {path['simulation_curve'][-1]['asset_value'] for path in result['debug_paths']}
    assert values == {round(800000 * .85 ** (33 / 12), 2)}
    for path in result['debug_paths']:
        row = path['simulation_curve'][-1]
        assert row['net_worth'] == pytest.approx(row['balance'] + row['investment_value'] + row['asset_value'], abs=.02)
    assert '車輛估值依固定折舊率計算，不抽樣。' in result['sampling_note']
    for key in ('p5', 'p50', 'p95'):
        assert result['real_net_worth_percentiles'][key] == pytest.approx(
            result['net_worth_percentiles'][key] / 1.02 ** 3, abs=.02)
