import copy
import re

import pytest
from fastapi.testclient import TestClient

from app.core.market_data import load_market_history
from app.decision_assumptions import ASSUMPTIONS
from app.services.calendar_period import YearMonth
from app.services.planner_vehicle import OWNERSHIP_FIELDS
from main import app


CLIENT = TestClient(app)
PROFILE = dict(salary=80000, fixed_expense=20000, variable_expense=15000,
               balance=1500000, inflation_rate=.02, raise_rate=.02)
DETAILS = dict(purchase_price=849000, payment_method='financed', down_payment=300000,
               loan_term_months=60, annual_interest_rate=.025)


def request(details=None, purchase='2027-03', months=60, inflation=.02):
    return dict(start_period='2026-11', months=months, inflation_rate=inflation,
                vehicles=[dict(name='買車', purchase_period=purchase, details=details or DETAILS)])


def vehicle_request(details, purchase):
    # Legacy vehicle API's base is the month BEFORE its first simulated month.
    # Both requests below therefore simulate 2026-11..2031-10, with the same
    # purchase date and initial finances, without changing legacy API semantics.
    payload = {'scenario_type': 'vehicle_purchase'}
    for key, value in details.items():
        payload[key] = value if key in ('payment_method', 'loan_term_months') else dict(value=value, source='user_provided')
    return dict(profile={**PROFILE, 'required_monthly_debt': 0}, start_period='2026-10',
                scenario=dict(scenario_id='consistency', scenario_type='vehicle_purchase',
                              target_period=purchase, horizon_months=60, payload=payload))


@pytest.mark.parametrize('payment', ['cash', 'financed'])
@pytest.mark.parametrize('purchase', ['2026-11', '2027-03', '2027-10', '2027-11', '2031-08'])
def test_planner_conversion_matches_every_vehicle_timeline_cash_balance(payment, purchase):
    details = DETAILS if payment == 'financed' else dict(purchase_price=849000, payment_method='cash')
    converted_response = CLIENT.post('/planner/vehicle-events', json=request(details, purchase))
    assert converted_response.status_code == 200, converted_response.json()
    converted = converted_response.json()
    vehicle = CLIENT.post('/decisions/vehicle', json=vehicle_request(details, purchase))
    assert vehicle.status_code == 200, vehicle.json()
    simulation = CLIENT.post('/simulate', json=dict(profile=PROFILE, months=60,
                                                  events=converted['events'], loans=converted['loans']))
    assert simulation.status_code == 200, simulation.json()
    curve = simulation.json()['result']['simulation_curve']
    reference = vehicle.json()
    assert [row['balance'] for row in curve] == [row['balance'] for row in reference['timeline']['scenario']]
    car = converted['vehicles'][0]
    assert car['monthly_loan_payment'] == reference['scenario']['monthly_loan_payment']
    assert car['total_loan_interest'] == reference['scenario']['total_loan_interest']
    assert car['one_time_cash'] == reference['scenario']['one_time_cash_requirement']
    assert car['purchase_month'] == YearMonth.parse('2026-11').months_until(YearMonth.parse(purchase)) + 1


def test_ownership_defaults_are_from_the_registry_and_user_zero_is_preserved():
    response = CLIENT.post('/planner/vehicle-events', json=request({**DETAILS, 'monthly_parking': 0}))
    assert response.status_code == 200
    data = response.json()
    # The planner-only depreciation default is listed after the ownership defaults.
    assert data['vehicles'][0]['defaults_used'] == [field for field in OWNERSHIP_FIELDS if field != 'monthly_parking'] + [
        'annual_depreciation_rate']
    for field in OWNERSHIP_FIELDS:
        event = next(event for event in data['events'] if event['name'] == field)
        expected = 0 if field == 'monthly_parking' else ASSUMPTIONS[field]['value'] / (12 if field.startswith('annual_') else 1)
        assert event['amount'] == -expected


@pytest.mark.parametrize('months,purchase', [(1, '2026-11'), (25, '2028-11'), (240, '2046-10'), (360, '2056-10')])
def test_horizon_end_including_partial_years_and_month_one(months, purchase):
    data = CLIENT.post('/planner/vehicle-events', json=request(purchase=purchase, months=months)).json()
    assert data['vehicles'][0]['purchase_month'] == months
    recurring = [event for event in data['events'] if event['type'] == 'range']
    assert len(recurring) == 5
    assert all(event['start_month'] == event['end_month'] == months for event in recurring)


def test_historical_inflation_fallback_and_multiple_vehicle_events_are_mc_compatible():
    payload = request(inflation=None, months=25)
    payload['vehicles'].append(dict(name='第二台車', purchase_period='2027-11',
                                    details=dict(purchase_price=100000, payment_method='cash')))
    response = CLIENT.post('/planner/vehicle-events', json=payload)
    assert response.status_code == 200
    data = response.json()
    rate = load_market_history().annual_inflation_rate
    assert data['inflation_rate_used'] == rate
    assert [car['purchase_month'] for car in data['vehicles']] == [5, 13]
    assert len(data['loans']) == 1
    assert 'Monte Carlo 的抽樣通膨不套用在購車成本上' in data['note']
    mc = CLIENT.post('/monte-carlo', json=dict(profile=PROFILE, months=25, simulations=3, seed=42,
                                            events=data['events'], loans=data['loans']))
    assert mc.status_code == 200
    second_year = next(event for event in data['events'] if event['name'] == 'monthly_parking' and event['start_month'] == 13)
    assert second_year['amount'] == -ASSUMPTIONS['monthly_parking']['value'] * (1 + rate)


@pytest.mark.parametrize('change', [
    lambda p: p['vehicles'][0].update(purchase_period='2026-10'),
    lambda p: p['vehicles'][0].update(purchase_period='2031-11'),
    lambda p: p['vehicles'][0].update(purchase_period='2027-13'),
    lambda p: p['vehicles'][0]['details'].pop('down_payment'),
    lambda p: p['vehicles'][0]['details'].pop('loan_term_months'),
    lambda p: p['vehicles'][0]['details'].pop('annual_interest_rate'),
    lambda p: p['vehicles'][0]['details'].update(down_payment=900000),
    lambda p: p['vehicles'][0]['details'].update(payment_method='cash'),
    lambda p: p['vehicles'][0]['details'].update(purchase_price=0),
    lambda p: p['vehicles'][0]['details'].update(loan_term_months=2.5),
    lambda p: p['vehicles'][0]['details'].update(monthly_parking=-1),
    lambda p: p['vehicles'][0]['details'].update(vehicle_catalog_id='unknown'),
])
def test_invalid_vehicle_inputs_return_chinese_422_without_private_input(change):
    payload = copy.deepcopy(request())
    change(payload)
    response = CLIENT.post('/planner/vehicle-events', json=payload)
    assert response.status_code == 422
    detail = response.json()['detail']
    messages = [detail] if isinstance(detail, str) else [error['msg'] for error in detail]
    assert all(re.search(r'[\u4e00-\u9fff]', message) for message in messages)
    assert 'input' not in response.text


def test_zero_interest_and_down_payment_are_valid_and_explicit_zero_inflation_wins():
    response = CLIENT.post('/planner/vehicle-events', json=request({**DETAILS, 'down_payment': 0, 'annual_interest_rate': 0}, inflation=0))
    assert response.status_code == 200
    data = response.json()
    assert data['inflation_rate_used'] == 0
    assert data['vehicles'][0]['one_time_cash'] == data['vehicles'][0]['total_loan_interest'] == 0
    assert data['vehicles'][0]['monthly_loan_payment'] == DETAILS['purchase_price'] / 60
