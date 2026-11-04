import pytest
from fastapi.testclient import TestClient

from app.vehicle_fees import (annual_vehicle_tax, insurance_reference, LICENSE_TAX_BANDS,
                              ROAD_FEE_BANDS, FIRST_TIME_GRADE_4)
from main import app

CLIENT = TestClient(app)


@pytest.mark.parametrize('fuel', ['gasoline', 'hybrid'])
@pytest.mark.parametrize('cc', [1498, 1798])
def test_toyota_official_calculator_cross_check_and_honda_band(cc, fuel):
    # Toyota's 13170 includes a separate 1250 registration fee; only 11920 recurs.
    result = annual_vehicle_tax(cc, fuel)
    assert (result['license_tax'], result['road_fee'], result['total']) == (7120, 4800, 11920)


@pytest.mark.parametrize('low,high,amount', LICENSE_TAX_BANDS)
def test_license_tax_every_band_boundary(low, high, amount):
    for cc in [low, high or low+1000]:
        assert annual_vehicle_tax(cc, 'gasoline')['license_tax'] == amount


@pytest.mark.parametrize('low,high,gas,diesel', ROAD_FEE_BANDS)
def test_road_fee_every_official_band_boundary_and_fuel_column(low, high, gas, diesel):
    for cc in [low, high]:
        assert annual_vehicle_tax(cc, 'gasoline')['road_fee'] == gas
        assert annual_vehicle_tax(cc, 'hybrid')['road_fee'] == gas
        assert annual_vehicle_tax(cc, 'diesel')['road_fee'] == diesel


@pytest.mark.parametrize('cc', [1, 250, 8001, 15000])
def test_blank_official_cells_require_manual_entry(cc):
    result = annual_vehicle_tax(cc, 'gasoline')
    assert result['road_fee'] is None and result['total'] is None
    assert '查無官方費額，請手動填寫' in result['notes']


def test_ev_exemption_is_explicitly_time_limited_and_sources_are_dated():
    result = annual_vehicle_tax(0, 'ev')
    assert [result[key] for key in ['license_tax', 'road_fee', 'total']] == [0, 0, 0]
    assert '2030-12-31' in result['notes'][0]
    assert '最快約 2030 年' in result['notes'][1]
    assert all(source['url'].startswith('https://') and source['checked_on']=='2026-11-02'
               and source['updated_on'] for source in result['sources'].values())


def test_insurance_reference_uses_official_grade_four_and_price_proportions():
    low = {item['id']:item for item in insurance_reference(500000)}
    high = {item['id']:item for item in insurance_reference(849000)}
    assert low['compulsory']['required'] is True
    assert low['compulsory']['default'] == 1398
    assert FIRST_TIME_GRADE_4[3]['female'] == 1318
    assert all(item['source']['url'].startswith('https://') for item in low.values())
    assert [high[id]['default'] for id in ['body_a','body_b','body_c']] == [44100,24600,10200]
    for id in ['body_a','body_b','body_c']:
        assert high[id]['default'] > low[id]['default']
        assert '依單一範例車款的比例估算' in high[id]['description']
    # 125000 * .029 = 3625 -> 3600; 125000 * .052 = 6500 exactly.
    assert next(i for i in insurance_reference(125000) if i['id']=='body_b')['default'] == 3600


@pytest.mark.parametrize('query', [
    {},dict(displacement_cc=0,fuel_type='gasoline',purchase_price=800000),
    dict(displacement_cc=-1,fuel_type='ev',purchase_price=800000),
    dict(displacement_cc=1798,fuel_type='other',purchase_price=800000),
    dict(displacement_cc=1798,fuel_type='gasoline',purchase_price='NaN'),
    dict(displacement_cc=1798,fuel_type='gasoline',purchase_price=0),
])
def test_reference_api_rejects_bad_parameters_with_chinese_errors(query):
    response = CLIENT.get('/planner/vehicle-fees', params=query)
    assert response.status_code == 422
    assert any('\u4e00' <= char <= '\u9fff' for char in response.text)


def test_reference_api_and_catalog_specs():
    response = CLIENT.get('/planner/vehicle-fees', params=dict(displacement_cc=1798,fuel_type='hybrid',purchase_price=849000))
    assert response.status_code == 200
    assert response.json()['tax']['total'] == 11920
    for car in CLIENT.get('/decisions/vehicle/catalog').json():
        assert car['displacement_cc'] > 0
        assert car['fuel_type'] in ('gasoline','hybrid','diesel')
        assert car['spec_source'].startswith('https://')


def request(details):
    return dict(start_period='2026-11',months=60,inflation_rate=.02,
                vehicles=[dict(name='買車',purchase_period='2027-03',details=details)])


BASE = dict(purchase_price=849000,payment_method='cash',annual_insurance=10000,annual_tax=11920)
ITEMS = [dict(id='compulsory',amount=1398),dict(id='third_party',amount=8602)]


@pytest.mark.parametrize('items,annual', [([],10000),([dict(id='theft',amount=10000)],10000),
    (ITEMS+[dict(id='body_a',amount=0),dict(id='body_b',amount=0)],10000),
    (ITEMS,9998),(ITEMS,None),(ITEMS+[dict(id='compulsory',amount=0)],10000),
    ([dict(id='compulsory',amount=-1)],-1),([dict(id='unknown',amount=10000)],10000)])
def test_insurance_detail_validation_is_chinese(items, annual):
    response=CLIENT.post('/planner/vehicle-events',json=request({**BASE,'insurance_items':items,'annual_insurance':annual}))
    assert response.status_code==422
    assert any('\u4e00' <= char <= '\u9fff' for char in response.text)


def test_saved_metadata_never_changes_conversion_and_legacy_still_works():
    legacy=CLIENT.post('/planner/vehicle-events',json=request(BASE))
    enriched=CLIENT.post('/planner/vehicle-events',json=request({**BASE,'insurance_items':ITEMS,
        'displacement_cc':1798,'fuel_type':'hybrid'}))
    assert legacy.status_code==enriched.status_code==200
    assert legacy.json()==enriched.json()
    # The specified tolerance accepts exactly one dollar, but not more.
    assert CLIENT.post('/planner/vehicle-events',json=request({**BASE,'insurance_items':ITEMS,'annual_insurance':10001})).status_code==200
    # Decimal cents must not turn an exact one-dollar tolerance into >1 due to binary floats.
    cents=[dict(id='compulsory',amount=100.1),dict(id='third_party',amount=100.2)]
    assert CLIENT.post('/planner/vehicle-events',json=request({**BASE,'insurance_items':cents,'annual_insurance':201.3})).status_code==200
    assert BASE == dict(purchase_price=849000,payment_method='cash',annual_insurance=10000,annual_tax=11920)
