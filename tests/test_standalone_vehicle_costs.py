import pytest
from fastapi.testclient import TestClient
from main import app


def data(method='cash',term=60):
    payload=dict(scenario_type='vehicle_purchase',payment_method=method,
                 purchase_price=dict(value=600000,source='user_provided'))
    for key in ['annual_insurance','annual_tax','annual_maintenance_budget','monthly_parking','monthly_fuel_or_energy']:
        payload[key]=dict(value=0,source='user_provided')
    if method=='financed':
        payload.update(down_payment=dict(value=120000,source='user_provided'),
                       annual_interest_rate=dict(value=0,source='user_provided'),loan_term_months=term)
    return dict(payload=payload)


@pytest.mark.parametrize('method,term,monthly,upfront,total,remaining',[
    ('cash',60,0,600000,600000,0),('financed',60,8000,120000,600000,0),('financed',120,4000,120000,360000,60)])
def test_standalone_costs_without_personal_profile(method,term,monthly,upfront,total,remaining):
    response=TestClient(app).post('/decisions/vehicle/costs',json=data(method,term))
    assert response.status_code==200
    result=response.json();costs=result['ownership_costs']
    assert costs['monthly_net_increase']==monthly
    assert costs['monthly_vehicle_outflow']==monthly
    assert costs['one_time_payment']==upfront
    assert costs['net_cash_outlay']==total
    assert costs['remaining_loan_months']==remaining
    assert 'affordability' not in result and 'timeline' not in result
    assert result['scope']=='vehicle_only'


def test_standalone_offsets_are_not_deducted_without_personal_expenses():
    request=data();request['payload']['monthly_transportation_offset']=dict(value=5000,source='user_provided')
    result=TestClient(app).post('/decisions/vehicle/costs',json=request).json()
    assert result['ownership_costs']['monthly_offset']==0
    assert 'transportation_offset' in result['excludes']


def test_personal_gross_outflow_is_separate_from_transportation_offset():
    from app.decision_schemas import VehicleDecisionRequest
    from app.services.vehicle_decision import resolve, ownership_cost_summary
    from app.services.scenario_engine import build_scenario
    from app.services.calendar_period import YearMonth
    payload=data('financed')['payload']
    payload['monthly_parking']=dict(value=1000,source='user_provided')
    payload['monthly_transportation_offset']=dict(value=500,source='user_provided')
    req=VehicleDecisionRequest.model_validate(dict(start_period='2000-01',
        profile=dict(salary=60000,balance=600000,fixed_expense=2000,variable_expense=1000,required_monthly_debt=0,inflation_rate=0,raise_rate=0),
        scenario=dict(scenario_id='test',scenario_type='vehicle_purchase',target_period='2000-02',horizon_months=60,payload=payload)))
    req,_=resolve(req)
    costs=ownership_cost_summary(req,build_scenario(req.scenario,YearMonth.parse(req.start_period)))
    assert costs['monthly_vehicle_outflow']==9000
    assert costs['monthly_net_increase']==8500
    assert costs['monthly_offset']==500


def test_standalone_validation_and_catalog_are_preserved():
    client=TestClient(app)
    request=data();request['vehicle_catalog_id']='toyota-cross-gas-luxury'
    assert client.post('/decisions/vehicle/costs',json=request).json()['selected_vehicle']['brand']=='Toyota'
    request['vehicle_catalog_id']='unknown'
    assert client.post('/decisions/vehicle/costs',json=request).status_code==422
    request=data('financed');request['payload']['down_payment']['value']=700000
    assert client.post('/decisions/vehicle/costs',json=request).status_code==422
    assert client.post('/decisions/vehicle/costs',json={**data(),'profile':{}}).status_code==422


@pytest.mark.parametrize('years',[1,3,5])
def test_ownership_period_and_annual_costs(years):
    request=data('financed');request['ownership_years']=years
    request['payload']['monthly_parking']=dict(value=1000,source='user_provided')
    response=TestClient(app).post('/decisions/vehicle/costs',json=request)
    assert response.status_code==200
    result=response.json();costs=result['ownership_costs']
    assert result['horizon_months']==years*12
    assert costs['net_cash_outlay']==120000+years*12*9000
    assert costs['remaining_loan_months']==60-years*12
    assert result['annual_running_cost']==12000
    parking=next(i for i in costs['items'] if i['key']=='monthly_parking')
    assert parking['annual_amount']==12000 and parking['period_total']==years*12000
    request['ownership_years']=2
    assert TestClient(app).post('/decisions/vehicle/costs',json=request).status_code==422
