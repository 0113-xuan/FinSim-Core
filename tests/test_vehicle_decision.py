import pytest
from decimal import Decimal, localcontext
from fastapi.testclient import TestClient
from main import app
from app.decision_schemas import VehicleDecisionRequest
from app.services.vehicle_decision import simulate_vehicle_decision, resolve, run_timeline, evaluate, price_metrics, ownership_cost_summary
from app.core.financial_rules import emergency_fund_months


@pytest.mark.parametrize('apr', ['0', '0.03', '0.075'])
def test_affordability_matches_independent_unrounded_annuity(apr):
    data = request_data()
    payload = data['scenario']['payload']
    payload['annual_interest_rate'] = sourced(apr)
    for key, value in dict(annual_insurance=18000, annual_tax=12000,
                           annual_maintenance_budget=12000, monthly_fuel_or_energy=2500,
                           monthly_parking=2000).items():
        payload[key] = sourced(value)
    with localcontext() as context:
        context.prec = 50
        rate = Decimal(apr) / 12
        payment = Decimal(20000)
        principal = payment * (1 - (1 + rate) ** -60) / rate if rate else payment * 60
        exact = Decimal(150000) + principal
    result = simulate_vehicle_decision(req(data))['affordability']
    actual = Decimal(str(result['maximum_affordable_vehicle_price']))
    assert Decimal(0) <= exact - actual <= Decimal('0.01')
    resolved, _ = resolve(req(data))
    _, below = price_metrics(resolved, float(actual))
    _, above = price_metrics(resolved, float(actual + Decimal('0.01')))
    assert all(c['passed'] for c in below)
    assert not next(c['passed'] for c in above if c['key'] == 'minimum_monthly_surplus')


def test_explicit_assumptions_keep_values_and_provenance():
    data = request_data()
    data['profile'].update(raise_rate=.01, inflation_rate=.04)
    data['constraints'] = dict(minimum_emergency_fund_months=4,
                               minimum_cash_balance=0, minimum_monthly_surplus=6000)
    data['assumption_sources'] = {key: 'system_assumption' for key in
                                 ['profile.raise_rate', 'profile.inflation_rate', *data['constraints']]}
    resolved, provenance = resolve(req(data))
    assert resolved.constraints.minimum_monthly_surplus == 6000
    assert resolved.profile.inflation_rate == .04
    assert all(p['source'] == 'system_assumption' for p in provenance
               if p['key'] in data['assumption_sources'])
    data['assumption_sources']['minimum_monthly_surplus'] = 'user'
    _, provenance = resolve(req(data))
    assert next(p['source'] for p in provenance if p['key'] == 'minimum_monthly_surplus') == 'user'
    data['assumption_sources']['unknown'] = 'user'
    with pytest.raises(ValueError):
        req(data)


def sourced(value):
    return dict(value=value, source='user_provided')


def request_data():
    return dict(profile=dict(salary=60000, fixed_expense=15000, variable_expense=10000,
                             balance=600000, required_monthly_debt=2000), start_period='2026-09',
                scenario=dict(scenario_id='car', scenario_type='vehicle_purchase', target_period='2026-10', horizon_months=60,
                              payload=dict(scenario_type='vehicle_purchase', payment_method='financed',
                                           purchase_price=sourced(650000), down_payment=sourced(150000),
                                           loan_term_months=60, annual_interest_rate=sourced(.03))))


def req(data=None):
    return VehicleDecisionRequest.model_validate(data or request_data())


def test_decision_deterministic_complete_and_boundary():
    result = simulate_vehicle_decision(req())
    assert result == simulate_vehicle_decision(req())
    assert result['scenario']['monthly_loan_payment'] == pytest.approx(8984.35)
    assert result['scenario']['total_loan_interest'] == pytest.approx(39061, abs=1)
    assert result['scenario']['one_time_cash_requirement'] == 150000
    assert len(result['stress_tests']) == 4
    assert result['affordability']['status'] == 'bounded'
    assert all(c['passed'] for c in result['affordability']['constraint_results'])
    assert any(not c['passed'] for c in result['affordability']['above_limit_constraint_results'])
    assert all('fsi' not in r for r in result['timeline']['scenario'])
    assert {x['source'] for x in result['provenance']} == {'user', 'system_assumption'}
    assert result['metric_source'] == 'derived'


def test_stresses_use_same_engine_and_unemployment_zero():
    resolved, _ = resolve(req())
    base, build = run_timeline(resolved)
    stressed, _ = run_timeline(resolved, stress='unemployment')
    assert [r['income'] for r in stressed[:3]] == [0, 0, 0]
    assert stressed[3]['income'] == base[3]['income']
    for name in ['unemployment', 'emergency_expense', 'income_reduction', 'interest_rate']:
        rows, _ = run_timeline(resolved, stress=name)
        assert rows[-1]['balance'] < base[-1]['balance']


def test_higher_prices_and_costs_cannot_improve_cash():
    resolved, _ = resolve(req())
    low, _ = price_metrics(resolved, 650000)
    high, _ = price_metrics(resolved, 750000)
    for key in ['ending_cash', 'minimum_cash_balance', 'monthly_surplus', 'minimum_emergency_fund_months']:
        assert high[key] <= low[key]
    resolved.scenario.payload.monthly_parking.value += 1000
    cost, _ = price_metrics(resolved, 650000)
    assert cost['ending_cash'] < low['ending_cash']


def test_offset_and_debt_counted_once():
    data = request_data()
    data['scenario']['payload']['monthly_transportation_offset'] = sourced(1000)
    resolved, _ = resolve(req(data))
    rows, build = run_timeline(resolved)
    ownership = 20000/12 + 12000/12 + 18000/12 + 3000 + 2000 - 1000
    assert rows[0]['debt_payment'] == pytest.approx(2000 + 8984.35)
    assert rows[0]['living_expense'] == pytest.approx(25000 + ownership, abs=.01)
    assert rows[0]['emergency_fund_months'] == pytest.approx(rows[0]['balance']/(rows[0]['living_expense']+rows[0]['debt_payment']), abs=.00001)
    assert rows[1]['net_cashflow'] - rows[0]['net_cashflow'] == 150000


def test_no_feasible_price_is_explicit():
    data = request_data()
    data['profile']['balance'] = 0
    result = simulate_vehicle_decision(req(data))
    assert result['affordability']['status'] == 'no_feasible_price'
    assert result['affordability']['maximum_affordable_vehicle_price'] is None


def test_canonical_coverage_includes_debt_and_handles_no_expense():
    assert emergency_fund_months(90000, 20000, 10000) == 3
    assert emergency_fund_months(90000, 0, 0) is None


def test_api_strict_validation_and_assumptions():
    client = TestClient(app)
    assert client.get('/decisions/vehicle/assumptions').status_code == 200
    assert client.post('/decisions/vehicle', json=request_data()).status_code == 200
    data = request_data()
    data['profile']['required_monthly_debt'] = -1
    assert client.post('/decisions/vehicle', json=data).status_code == 422


@pytest.mark.parametrize('field', ['annual_insurance', 'annual_tax', 'annual_maintenance_budget', 'monthly_fuel_or_energy', 'monthly_parking'])
def test_explicit_zero_overrides_assumption(field):
    data = request_data()
    data['scenario']['payload'][field] = sourced(0)
    resolved, provenance = resolve(req(data))
    assert getattr(resolved.scenario.payload, field).value == 0
    assert next(p for p in provenance if p['key'] == field)['source'] == 'user'


def test_decision_inflation_and_cash_purchase():
    data = request_data()
    p = data['scenario']['payload']
    p['payment_method'] = 'cash'
    for key in ['down_payment', 'loan_term_months', 'annual_interest_rate']:
        del p[key]
    low, _ = resolve(req(data))
    high = low.model_copy(deep=True)
    low.profile.inflation_rate = .01
    high.profile.inflation_rate = .05
    low_rows, build = run_timeline(low)
    high_rows, _ = run_timeline(high)
    assert high_rows[-1]['balance'] < low_rows[-1]['balance']
    assert evaluate(low_rows, low, build)['monthly_loan_payment'] == 0


def test_new_path_does_not_call_legacy_risk_or_ai(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Legacy risk or AI called')
    monkeypatch.setattr('app.core.simulation.calculate_fsi', forbidden)
    monkeypatch.setattr('app.core.simulation.classify_risk', forbidden)
    monkeypatch.setattr('app.core.advisor.compare_options', forbidden)
    monkeypatch.setattr('app.services.ai_provider.get_ai_provider', forbidden)
    simulate_vehicle_decision(req())


def test_search_limit_is_not_misreported_as_boundary():
    data = request_data()
    data['profile']['salary'] = 50000000
    data['profile']['balance'] = 5000000000
    assert simulate_vehicle_decision(req(data))['affordability']['status'] == 'search_limit_reached'


def test_invalid_dates_offsets_and_rates_rejected():
    client = TestClient(app)
    for key, value in [('annual_interest_rate', 1), ('monthly_transportation_offset', 30000)]:
        data = request_data()
        data['scenario']['payload'][key] = sourced(value)
        assert client.post('/decisions/vehicle', json=data).status_code == 422
    data = request_data()
    data['scenario']['target_period'] = '2026-09'
    assert client.post('/decisions/vehicle', json=data).status_code == 422


@pytest.mark.parametrize('cash,term,target', [(False, 36, '2026-10'), (False, 84, '2027-10'), (True, 60, '2026-10')])
def test_ownership_cash_totals_match_engine_without_double_counting(cash, term, target):
    data = request_data()
    data['scenario']['target_period'] = target
    p = data['scenario']['payload']
    p['monthly_transportation_offset'] = sourced(1000)
    p['loan_term_months'] = term
    if cash:
        p['payment_method'] = 'cash'
        for key in ['down_payment', 'annual_interest_rate', 'loan_term_months']:
            del p[key]
    resolved, _ = resolve(req(data))
    rows, build = run_timeline(resolved)
    baseline, _ = run_timeline(resolved, baseline=True)
    costs = ownership_cost_summary(resolved, build)
    assert costs['net_cash_outlay'] == pytest.approx(baseline[-1]['balance'] - rows[-1]['balance'], abs=.01)
    assert costs['one_time_payment'] == (650000 if cash else 150000)
    assert costs['remaining_loan_months'] == (0 if cash or term == 36 else 36)
    assert costs['monthly_net_increase'] == pytest.approx(costs['monthly_ownership'] + costs['monthly_loan_payment'] - costs['monthly_offset'], abs=.01)
    assert len(costs['items']) == 6
    displayed_total = costs['one_time_payment'] + costs['loan_payments_total'] + costs['rounding_adjustment'] + sum(i['period_total'] * (-1 if i['is_offset'] else 1) for i in costs['items'])
    assert costs['net_cash_outlay'] == pytest.approx(displayed_total, abs=.001)
    assert next(i for i in costs['items'] if i['key'] == 'monthly_transportation_offset')['is_offset']


def test_zero_ownership_budget_and_short_loan():
    data = request_data()
    data['profile']['inflation_rate'] = 0
    for key in ['annual_insurance', 'annual_tax', 'annual_maintenance_budget', 'monthly_fuel_or_energy', 'monthly_parking', 'monthly_transportation_offset']:
        data['scenario']['payload'][key] = sourced(0)
    data['scenario']['payload']['loan_term_months'] = 12
    resolved, _ = resolve(req(data))
    _, build = run_timeline(resolved)
    costs = ownership_cost_summary(resolved, build)
    assert costs['monthly_ownership'] == 0
    assert costs['loan_payments_total'] == pytest.approx(costs['monthly_loan_payment'] * 12)
    assert costs['net_cash_outlay'] == pytest.approx(costs['one_time_payment'] + costs['loan_payments_total'])
