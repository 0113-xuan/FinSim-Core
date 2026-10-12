from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from main import app


def request_data():
    return dict(left=dict(vehicle_id='toyota-cross-gas-luxury'),
                right=dict(vehicle_id='toyota-cross-hybrid-luxury'),
                annual_distance_km=15000, fuel_price_twd_l=30, ownership_years=5)


@pytest.mark.parametrize('years',[1,3,5])
def test_direct_comparison_monthly_costs_and_structure(years):
    data=request_data();data['ownership_years']=years
    response=TestClient(app).post('/decisions/vehicle/cost-comparison',json=data)
    assert response.status_code == 200
    result=response.json()
    assert result['left']['monthly_cost'] == pytest.approx(8789.05)
    assert result['right']['monthly_cost'] == pytest.approx(7762.41)
    assert result['left']['annual_cost'] == pytest.approx(105468.56)
    assert result['left']['period_cost'] == pytest.approx(105468.56 * years)
    assert result['difference_right_minus_left']['monthly_cost'] == -1026.64
    for side in ['left','right']:
        assert sum(Decimal(str(item['percentage'])) for item in result[side]['structure']) == Decimal(100)
        assert len(result[side]['structure']) == 5
        assert result[side]['budgets']['annual_insurance']['source'] == 'system_assumption'
    assert 'purchase_price' in result['excludes'] and 'depreciation' in result['excludes']


def test_same_car_zero_costs_and_user_budgets():
    data=request_data();data['right']=data['left'].copy()
    data['annual_distance_km']=0
    for side in ['left','right']:
        for key in ['annual_insurance','annual_tax','annual_maintenance_budget','monthly_parking']:
            data[side][key]=dict(value=0,source='user_provided')
    client=TestClient(app)
    result=client.post('/decisions/vehicle/cost-comparison',json=data).json()
    assert result['left']['monthly_cost'] == result['right']['monthly_cost'] == 0
    assert all(item['percentage'] == 0 for item in result['left']['structure'])
    assert result['difference_right_minus_left']['monthly_cost'] == 0
    data['right']['monthly_parking']['value']=1000
    result=client.post('/decisions/vehicle/cost-comparison',json=data).json()
    assert result['right']['monthly_cost'] == 1000
    assert result['right']['period_cost'] == 60000
    assert result['right']['budgets']['monthly_parking']['source'] == 'user_provided'


def test_strict_validation_without_financial_profile_or_ai():
    client=TestClient(app)
    for key,value in [('ownership_years',2),('annual_distance_km',-1),('fuel_price_twd_l','NaN'),('extra',True)]:
        assert client.post('/decisions/vehicle/cost-comparison',json={**request_data(),key:value}).status_code == 422
    data=request_data();data['left']['vehicle_id']='unknown'
    assert client.post('/decisions/vehicle/cost-comparison',json=data).status_code == 422
    for budget in [dict(value=-1),dict(value='Infinity'),dict(value=100,source='AI')]:
        data=request_data();data['left']['annual_tax']=budget
        assert client.post('/decisions/vehicle/cost-comparison',json=data).status_code == 422


def test_custom_vehicle_comparison_preserves_user_amounts():
    data=request_data()
    data['left']=dict(custom_vehicle=dict(name='我的二手車',monthly_fuel_or_energy=dict(value=1000,source='user_provided')))
    response=TestClient(app).post('/decisions/vehicle/cost-comparison',json=data)
    assert response.status_code == 200
    result=response.json()['left']
    assert result['vehicle']['model']=='我的二手車'
    assert result['vehicle']['source']=='user_provided'
    fuel=next(i for i in result['structure'] if i['key']=='monthly_fuel_or_energy')
    assert fuel['monthly_amount']==1000 and fuel['source']=='user_provided'
    assert 'price_twd' not in result['vehicle']
    data['right']=data['left'].copy()
    assert TestClient(app).post('/decisions/vehicle/cost-comparison',json=data).json()['difference_right_minus_left']['monthly_cost']==0


def test_custom_vehicle_rejects_missing_conflicting_or_invalid_input():
    for selection in [{},dict(vehicle_id='toyota-cross-gas-luxury',custom_vehicle=dict(name='車',monthly_fuel_or_energy=dict(value=1))),dict(custom_vehicle=dict(name=' ',monthly_fuel_or_energy=dict(value=1))),dict(custom_vehicle=dict(name='車',monthly_fuel_or_energy=dict(value=-1)))]:
        data=request_data();data['left']=selection
        assert TestClient(app).post('/decisions/vehicle/cost-comparison',json=data).status_code==422


def financial_context():
    return dict(profile=dict(salary=60000,balance=600000,fixed_expense=15000,variable_expense=10000,
                             required_monthly_debt=0,raise_rate=0,inflation_rate=.02),
                start_period='2026-10',target_period='2026-11',
                constraints=dict(minimum_monthly_surplus=5000,minimum_cash_balance=0,minimum_emergency_fund_months=3))


def test_financial_comparison_uses_same_profile_and_engine_with_loan():
    data=request_data();data['financial_context']=financial_context()
    for side in ['left','right']:
        data[side].update(payment_method='financed',down_payment=150000,annual_interest_rate=.03,loan_term_months=60)
    response=TestClient(app).post('/decisions/vehicle/cost-comparison',json=data)
    assert response.status_code==200
    result=response.json()
    assert result['left']['financial']['baseline']==result['right']['financial']['baseline']
    assert result['left']['financial']['metrics']['monthly_loan_payment']>0
    assert result['left']['financial']['source']=='derived'
    assert result['financial_difference_right_minus_left']['monthly_surplus']==round(result['right']['financial']['metrics']['monthly_surplus']-result['left']['financial']['metrics']['monthly_surplus'],2)
    # Cross-check the independently invoked existing decision endpoint.
    payload=dict(scenario_type='vehicle_purchase',payment_method='financed',purchase_price=dict(value=809000,source='backend_normalized'),
                 down_payment=dict(value=150000,source='user_provided'),annual_interest_rate=dict(value=.03,source='user_provided'),loan_term_months=60,
                 monthly_fuel_or_energy=dict(value=2622.38,source='derived'))
    standalone=TestClient(app).post('/decisions/vehicle',json=dict(profile=data['financial_context']['profile'],constraints=data['financial_context']['constraints'],start_period='2026-10',
        scenario=dict(scenario_id='reference',scenario_type='vehicle_purchase',target_period='2026-11',horizon_months=60,payload=payload)))
    assert standalone.status_code==200
    assert result['left']['financial']['metrics']==standalone.json()['scenario']


def test_custom_financial_comparison_requires_real_price_and_valid_dates():
    data=request_data();data['financial_context']=financial_context()
    data['left']=dict(custom_vehicle=dict(name='自訂',monthly_fuel_or_energy=dict(value=1000)))
    assert TestClient(app).post('/decisions/vehicle/cost-comparison',json=data).status_code==422
    data['left']['custom_vehicle']['purchase_price']=500000
    assert TestClient(app).post('/decisions/vehicle/cost-comparison',json=data).status_code==200
    data['financial_context']['target_period']='2026-10'
    assert TestClient(app).post('/decisions/vehicle/cost-comparison',json=data).status_code==422
