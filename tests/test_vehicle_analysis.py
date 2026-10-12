from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from main import app
from app.decision_schemas import VehicleDecisionRequest, VehicleComparisonRequest
from app.services.vehicle_analysis import sensitivity_analysis, compare_vehicles
from app.services.vehicle_decision import resolve, run_timeline


def data():
    return dict(profile=dict(salary=60000, balance=600000, fixed_expense=15000,
                             variable_expense=10000, required_monthly_debt=2000),
                start_period='2026-09', scenario=dict(scenario_id='car', scenario_type='vehicle_purchase',
                target_period='2026-10', horizon_months=60, payload=dict(scenario_type='vehicle_purchase',
                payment_method='financed', purchase_price=dict(value=650000, source='user_provided'),
                down_payment=dict(value=150000, source='user_provided'), loan_term_months=60,
                annual_interest_rate=dict(value=.03, source='user_provided'))))


def request(raw=None):
    return VehicleDecisionRequest.model_validate(raw or data())


def test_debts_stop_after_last_payment_and_do_not_count_twice():
    raw = data()
    raw['profile'].update(required_monthly_debt=0, existing_debts=[
        dict(name='student', monthly_payment=8000, remaining_months=14),
        dict(name='card', monthly_payment=1000, remaining_months=1),
        dict(name='paid', monthly_payment=999, remaining_months=0)])
    req, _ = resolve(request(raw))
    rows, _ = run_timeline(req, baseline=True)
    assert [r['debt_payment'] for r in rows[:2]] == [9000, 8000]
    assert rows[13]['debt_payment'] == 8000
    assert rows[14]['debt_payment'] == 0
    financed, _ = run_timeline(req)
    assert financed[14]['debt_payment'] == pytest.approx(8984.35)
    raw['profile']['required_monthly_debt'] = 1
    with pytest.raises(ValueError):
        request(raw)


def test_legacy_debt_stays_constant_and_invalid_terms_rejected():
    req, _ = resolve(request())
    rows, _ = run_timeline(req, baseline=True)
    assert all(r['debt_payment'] == 2000 for r in rows)
    for months in (-1, 1.5, '14'):
        raw = data()
        raw['profile'].update(required_monthly_debt=0, existing_debts=[dict(name='loan', monthly_payment=1, remaining_months=months)])
        with pytest.raises(ValueError):
            request(raw)


def test_sensitivity_is_deterministic_sorted_and_does_not_mutate():
    req = request()
    before = req.model_dump()
    result = sensitivity_analysis(req)
    assert req.model_dump() == before
    assert result == sensitivity_analysis(req)
    assert len(result['factors']) == 7
    spans = [f['impact_span'] for f in result['factors']]
    assert spans == sorted(spans, reverse=True)
    salary = next(f for f in result['factors'] if f['key'] == 'salary')
    assert salary['low']['ending_cash_change'] == -360000
    assert salary['high']['ending_cash_change'] == 360000
    for f in result['factors']:
        if f['key'] != 'salary':
            assert f['high']['ending_cash_change'] <= f['low']['ending_cash_change']


def test_invalid_price_endpoint_not_silently_changed_and_zero_inflation_clamped():
    raw = data()
    raw['scenario']['payload']['down_payment']['value'] = 640000
    raw['profile']['inflation_rate'] = 0
    result = sensitivity_analysis(request(raw))
    price = next(f for f in result['factors'] if f['key'] == 'purchase_price')
    assert price['low']['status'] == 'not_applicable'
    assert price['low']['metrics'] is None
    inflation = next(f for f in result['factors'] if f['key'] == 'inflation_rate')
    assert inflation['low']['value'] == 0
    assert inflation['low']['ending_cash_change'] == 0


def test_comparison_identical_inputs_and_shared_context():
    raw = data()
    before = deepcopy(raw)
    result = compare_vehicles(VehicleComparisonRequest.model_validate(dict(a=raw, b=raw)))
    assert all(value == 0 for value in result['difference_b_minus_a'].values())
    assert result['a'] == result['b']
    assert raw == before
    assert any(p['source'] == 'system_assumption' for p in result['a']['provenance'])
    different = deepcopy(raw)
    different['profile']['salary'] += 1
    with pytest.raises(ValueError):
        VehicleComparisonRequest.model_validate(dict(a=raw, b=different))


def test_comparison_later_purchase_uses_same_observation_period():
    a = data()
    b = deepcopy(a)
    b['scenario']['target_period'] = '2027-10'
    result = compare_vehicles(VehicleComparisonRequest.model_validate(dict(a=a, b=b)))
    assert [r['period'] for r in result['a']['timeline']['scenario']] == [r['period'] for r in result['b']['timeline']['scenario']]
    assert result['b']['scenario']['ending_cash'] > result['a']['scenario']['ending_cash']


def test_analysis_api_validation_and_registry_metadata():
    client = TestClient(app)
    assert client.post('/decisions/vehicle/sensitivity', json=data()).status_code == 200
    invalid = data()
    invalid['unexpected'] = 123
    assert client.post('/decisions/vehicle/sensitivity', json=invalid).status_code == 422
    b = data()
    b['start_period'] = '2026-08'
    assert client.post('/decisions/vehicle/compare', json=dict(a=data(), b=b)).status_code == 422
    for item in client.get('/decisions/vehicle/assumptions').json():
        assert item['source_date'] is None
        assert item['reference'] is None
        assert item['calibration_status'] == 'planning_assumption'
        assert item['user_override'] is False


def test_assumption_actual_values_overrides_and_missing_source_dates():
    from app.services.vehicle_decision import effective_assumptions
    raw = data()
    raw['scenario']['payload']['annual_insurance'] = dict(value=0, source='user_provided')
    req, provenance = resolve(request(raw))
    items = {x['key']: x for x in effective_assumptions(req, provenance)}
    assert items['annual_insurance']['value'] == 0
    assert items['annual_insurance']['default_value'] == 20000
    assert items['annual_insurance']['user_override'] is True
    assert items['annual_tax']['source'] == 'system_assumption'
    assert items['annual_tax']['user_override'] is False


@pytest.mark.parametrize('field,change,expected', [('salary', -5000, -300000),
                                                  ('monthly_parking', 1000, -60000)])
def test_custom_change_matches_independent_cash_flow(field, change, expected):
    from app.decision_schemas import VehicleWhatIfRequest
    from app.services.vehicle_analysis import vehicle_what_if
    raw = data()
    raw['profile']['inflation_rate'] = 0
    before = deepcopy(raw)
    result = vehicle_what_if(VehicleWhatIfRequest.model_validate(dict(request=raw, field=field, change=change)))
    assert result['variant']['ending_cash_change'] == expected
    assert result['variant']['metrics']['ending_cash'] - result['base_metrics']['ending_cash'] == expected
    assert raw == before


def test_custom_invalid_amount_and_unsupported_field_are_controlled():
    client = TestClient(app)
    result = client.post('/decisions/vehicle/what-if', json=dict(request=data(), field='salary', change=-70000))
    assert result.status_code == 200
    assert result.json()['variant']['status'] == 'not_applicable'
    assert result.json()['variant']['metrics'] is None
    invalid_price = client.post('/decisions/vehicle/what-if', json=dict(request=data(), field='purchase_price', change=-600000))
    assert invalid_price.json()['variant']['status'] == 'not_applicable'
    assert client.post('/decisions/vehicle/what-if', json=dict(request=data(), field='unknown', change=1)).status_code == 422
    assert client.post('/decisions/vehicle/what-if', json=dict(request=data(), field='salary', change='NaN')).status_code == 422
