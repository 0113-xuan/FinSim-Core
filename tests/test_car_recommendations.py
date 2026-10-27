"""P2 has no network or external AI dependency."""
import json
import subprocess
from datetime import date, datetime
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.recommendation_catalog import recommendation_catalog, record
from app.recommendation_schemas import CarNeedsRequest
from app.services.car_recommendations import recommend_cars
from main import app


@pytest.fixture
def needs():
    return dict(schema_version='1.0', revision=12, status='confirmed', currency='TWD',
        background=dict(occupation='employee'),
        constraints=dict(budget_max=2000000, budget_basis='vehicle_price', min_seats=3, avoid_body_types=[]),
        usage=dict(purposes=['commute'], monthly_distance_km=1000, usual_passengers=3, ownership_years=5,
                   parking_type='own', monthly_parking=0, home_charging='yes', public_charging='unknown'),
        preferences=dict(body_types=[], priorities=['comfort'], powertrains=[]),
        financial_profile=None,
        payment=dict(payment_method='cash', down_payment=None, annual_interest_rate=None, loan_term_months=None),
        free_text='', extraction=dict(provider='mock', is_real_ai=False, status='not_requested', candidates=[]),
        field_sources={}, recommendation_handoff=dict(status='ready_for_p2', engine_connected=False))


def run(needs):
    return recommend_cars(CarNeedsRequest.model_validate(needs))


def test_curated_catalog_has_sources_non_suv_and_all_powertrains():
    cars = recommendation_catalog()
    assert 6 <= len(cars) <= 8
    assert len({c['model'] for c in cars if c['body_type'] != 'suv'}) >= 2
    assert {c['powertrain'] for c in cars} == {'ice', 'hev', 'bev'}
    assert all(c['source_type'] == 'official' and c['sources']['price'].startswith('https://') for c in cars)
    assert all(c['checked_on'] and c['model_year_note'] for c in cars)


@pytest.mark.parametrize('change,reason', [('budget','預算'), ('seats','座位'), ('suv','排除')])
def test_hard_filters(needs, change, reason):
    if change == 'budget': needs['constraints']['budget_max'] = 100000
    if change == 'seats': needs['constraints']['min_seats'] = needs['usage']['usual_passengers'] = 7
    if change == 'suv': needs['constraints']['avoid_body_types'] = ['suv']
    result = run(needs)
    assert result['excluded']
    assert all(any(reason in r for r in item['reasons']) for item in result['excluded'])
    if change != 'suv': assert result['ranked'] == []
    else: assert all(i['vehicle']['body_type'] != 'suv' for i in result['ranked'])


def test_missing_catalog_values_are_not_zero_or_false_exclusions(needs, monkeypatch):
    cars = recommendation_catalog()
    cars[0]['price_twd'] = None
    cars[1]['seats'] = None
    cars[2]['efficiency'] = None
    monkeypatch.setattr('app.services.car_recommendations.recommendation_catalog', lambda: cars)
    result = run(needs)
    assert len(result['incomplete']) == 4
    assert result['excluded'] == []
    assert all(i['five_year_cash_outflow'] is None for i in result['incomplete'])


def test_ranking_changes_with_mileage_and_does_not_use_occupation(needs):
    needs['usage']['monthly_distance_km'] = 0
    low = run(needs)
    needs['usage']['monthly_distance_km'] = 12000
    high = run(needs)
    assert low['ranked'][0]['vehicle']['id'] == 'altis-classic'
    assert high['ranked'][0]['vehicle']['id'] == 'fit-hev'
    needs['background']['occupation'] = 'sales'
    assert high['ranked'] == run(needs)['ranked']


def test_cash_financing_and_remaining_payments_are_explicit(needs):
    cash = run(needs)['ranked'][0]
    needs['payment'] = dict(payment_method='financed', down_payment=200000, annual_interest_rate=.025, loan_term_months=84)
    loan = run(needs)['ranked'][0]
    assert loan['costs']['remaining_loan_months'] == 24
    assert loan['remaining_loan_payments'] == round(24*loan['costs']['monthly_loan_payment'], 2)
    assert cash['costs']['monthly_loan_payment'] == 0
    recurring = sum(i['period_total'] for i in loan['costs']['items']) + loan['costs']['rounding_adjustment']
    assert loan['five_year_cash_outflow'] == pytest.approx(200000+loan['costs']['loan_payments_total']+recurring, abs=.01)
    assert loan['costs']['monthly_vehicle_outflow'] > loan['costs']['monthly_ownership']


def test_affordability_is_separate_from_ranking(needs):
    profile = dict(salary=100000, balance=2000000, fixed_expense=10000, variable_expense=10000, required_monthly_debt=0)
    needs['financial_profile'] = profile
    wealthy = run(needs)
    assert all(i['affordability']['passed'] for i in wealthy['ranked'])
    profile.update(salary=10000, balance=0)
    poor = run(needs)
    assert all(not i['affordability']['passed'] for i in poor['ranked'])
    assert [i['vehicle']['id'] for i in wealthy['ranked']] == [i['vehicle']['id'] for i in poor['ranked']]
    assert poor['ranked'][0]['affordability']['metrics']['ending_cash'] < 0


def test_preferences_unknowns_and_bev_are_not_invented(needs):
    needs['preferences'].update(body_types=['sedan'], powertrains=['bev'])
    result = run(needs)
    assert len(result['ranked']) == 6
    assert result['incomplete'][0]['vehicle']['powertrain'] == 'bev'
    assert result['incomplete'][0]['five_year_cash_outflow'] is None
    assert next(i for i in result['ranked'] if i['vehicle']['body_type'] == 'suv')['preferences'][0]['status'] == 'mismatch'
    assert result['ranked'][0]['preferences'][-1]['status'] == 'insufficient_data'


@pytest.mark.parametrize('field', ['monthly_distance_km', 'monthly_parking'])
def test_missing_user_cost_inputs_require_completion(needs, field):
    needs['usage'][field] = None
    result = run(needs)
    assert result['ranked'] == [] and result['missing_inputs']
    assert len(result['incomplete']) == 7


@pytest.mark.parametrize('mutation', [
    lambda n: n.update(price_twd=1),
    lambda n: n.update(vehicle_catalog_id='fake'),
    lambda n: n['usage'].update(monthly_fuel_or_energy=0),
    lambda n: n['constraints'].update(budget_max=-1),
    lambda n: n['constraints'].update(budget_max=True),
    lambda n: n['constraints'].update(budget_max='1000000'),
    lambda n: n['constraints'].update(min_seats=1),
    lambda n: n['preferences'].update(powertrains=['diesel']),
    lambda n: n.update(status='draft'),
    lambda n: n['payment'].update(payment_method='financed'),
    lambda n: n['payment'].update(down_payment=1),
])
def test_backend_rejects_forged_or_invalid_handoff(needs, mutation):
    mutation(needs)
    with TestClient(app) as client:
        assert client.post('/decisions/vehicle/recommendations', json=needs).status_code == 422


def test_api_valid_response_and_original_catalog_unchanged(needs):
    with TestClient(app) as client:
        before = client.get('/decisions/vehicle/catalog').json()
        response = client.post('/decisions/vehicle/recommendations', json=needs)
        assert response.status_code == 200, response.text
        assert response.json()['provider'] == 'deterministic'
        assert client.get('/decisions/vehicle/catalog').json() == before
        assert len(before) == 5


def test_actual_p1_serialization_is_accepted():
    root = Path(__file__).resolve().parents[1]
    code = "const m=require('./static/car-needs-state.js');let s=m.createState();Object.assign(s.answers,{budget_max:1000000,purposes:['commute'],usual_passengers:3,ownership_years:5,monthly_distance_km:1000,payment_method:'cash',parking_type:'own',monthly_parking:0});console.log(JSON.stringify(m.serialize(m.confirm(s))));"
    output = subprocess.run(['node', '-e', code], cwd=root, capture_output=True, text=True, check=True)
    result = run(json.loads(output.stdout))
    assert len(result['ranked']) == 6


def test_user_growth_assumption_is_reported(needs):
    needs['financial_profile'] = dict(salary=50000, balance=900000, fixed_expense=10000, variable_expense=10000, required_monthly_debt=0, inflation_rate=.03)
    result = run(needs)
    inflation = next(a for a in result['assumptions'] if a['key'] == 'inflation_rate')
    assert inflation['value'] == .03 and inflation['source'] == 'user_provided'


def test_no_charging_is_explicit_exclusion_unknown_is_not(needs):
    needs['usage'].update(home_charging='no', public_charging='no')
    result = run(needs)
    assert any('充電' in item['reasons'][0] for item in result['excluded'])
    needs['usage']['public_charging'] = 'unknown'
    assert not run(needs)['excluded']


def test_actual_price_rechecks_down_payment(needs):
    needs['payment'] = dict(payment_method='financed', down_payment=900000, annual_interest_rate=0, loan_term_months=60)
    result = run(needs)
    assert all(i['vehicle']['price_twd'] > 900000 for i in result['ranked'])
    assert any('頭期款' in reason for i in result['incomplete'] for reason in i['reasons'])


def test_missing_payment_and_foreign_currency(needs):
    needs['payment']['payment_method'] = None
    assert run(needs)['ranked'] == []
    needs['currency'] = 'USD'
    with TestClient(app) as client:
        assert client.post('/decisions/vehicle/recommendations', json=needs).status_code == 422


@pytest.mark.parametrize('token', ['NaN', 'Infinity', '-Infinity', '1e9999'])
def test_nonfinite_in_actual_recommendation_field(needs, token):
    content = json.dumps(needs).replace('"budget_max": 2000000', '"budget_max": '+token)
    response = TestClient(app).post('/decisions/vehicle/recommendations', content=content, headers={'content-type':'application/json'})
    assert response.status_code == 422
    assert response.json()['detail'][0]['type'] == 'json_invalid'


def test_record_requires_explicit_seats_and_source():
    args = ('fixture', 'Fixture', 'Test', 'Test', 100, 'mpv', 'ice', 10, 'https://example.test', None)
    with pytest.raises(TypeError):
        record(*args)
    for seats in (5, 7, None):
        car = record(*args, seats=seats, seats_source='https://example.test/seats' if seats else None,
                     seats_source_type='unknown', seats_verification='unverified', seats_note='Synthetic test fixture, not a real vehicle')
        assert car['seats'] == seats
    with pytest.raises(ValueError):
        record(*args, seats=5, seats_source=None, seats_source_type='unknown', seats_verification='unverified', seats_note='fixture')


def test_five_seven_and_unknown_seat_filtering(needs, monkeypatch):
    # Synthetic copies test filtering, not new production catalog specifications.
    cars = recommendation_catalog()[:3]
    for car, seats in zip(cars, [5, 7, None]):
        car['seats'] = seats
    monkeypatch.setattr('app.services.car_recommendations.recommendation_catalog', lambda: cars)
    needs['constraints']['min_seats'] = needs['usage']['usual_passengers'] = 7
    result = run(needs)
    assert [i['vehicle']['seats'] for i in result['ranked']] == [7]
    assert [i['vehicle']['seats'] for i in result['excluded']] == [5]
    assert [i['vehicle']['seats'] for i in result['incomplete']] == [None]
    assert '座位數未知' in result['incomplete'][0]['reasons'][0]


def test_catalog_seats_have_per_field_provenance():
    for car in recommendation_catalog():
        assert car['sources']['seats'].startswith('https://')
        assert car['source_types']['seats'] in ('official', 'government', 'third_party')
        assert car['verification']['seats'] in ('verified', 'indexed_only')
        assert car['verification_notes']['seats']
        assert car['verification']['model_year'] == 'unverified'


@pytest.mark.parametrize('reference,start,target', [
    (date(2026,1,31),'2026-01','2026-02'), (date(2026,2,1),'2026-02','2026-03'),
    (date(2026,12,31),'2026-12','2027-01'), (date(2027,1,1),'2027-01','2027-02'),
    (date(2028,2,29),'2028-02','2028-03')])
def test_fixed_reference_date_preserves_next_month_purchase(needs, reference, start, target):
    result = recommend_cars(CarNeedsRequest.model_validate(needs), reference_date=reference)
    assert result['reference_date'] == reference.isoformat()
    assert result['timezone'] == 'Asia/Taipei'
    assert result['start_period'] == start and result['purchase_period'] == target


@pytest.mark.parametrize('utc_instant,start,target', [
    ('2026-01-31T15:59:59+00:00','2026-01','2026-02'),
    ('2026-01-31T16:00:00+00:00','2026-02','2026-03'),
    ('2026-12-31T15:59:59+00:00','2026-12','2027-01'),
    ('2026-12-31T16:00:00+00:00','2027-01','2027-02')])
def test_utc_host_uses_taipei_month(needs, monkeypatch, utc_instant, start, target):
    instant = datetime.fromisoformat(utc_instant)
    class Clock:
        @classmethod
        def now(cls, zone):
            assert zone.key == 'Asia/Taipei'
            return instant.astimezone(zone)
    monkeypatch.setattr('app.services.calendar_period.datetime', Clock)
    result = run(needs)
    assert result['start_period'] == start and result['purchase_period'] == target


def test_reference_month_does_not_change_sixty_month_costs_or_order(needs):
    req = CarNeedsRequest.model_validate(needs)
    a = recommend_cars(req, reference_date=date(2026,1,31))
    b = recommend_cars(req, reference_date=date(2027,12,1))
    assert [(i['vehicle']['id'],i['five_year_cash_outflow'],i['remaining_loan_payments']) for i in a['ranked']] == [(i['vehicle']['id'],i['five_year_cash_outflow'],i['remaining_loan_payments']) for i in b['ranked']]
