import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.parking import parse_monthly_rent, normalize_tdx, load_parking_snapshot, parking_reference
from scripts.fetch_tdx_parking import build_snapshot
from main import app

CLIENT=TestClient(app)
FIXTURE=Path(__file__).parent/'fixtures/parking/multi_city'
# These are synthetic examples, NOT quotes from real TDX records. Anonymous
# TDX access returned 401 on 2026-11-03; replace/extend after a real download.
CASES=[
    ('月租2,000元',2000),('月票：3,500元',3500),('包月 NT$2,800',2800),
    ('定期票每月3000元',3000),('月租２，５００元',2500),
    ('日間月票 2,000 元、全日月票 3,500 元',3500),
    ('全日月票2000元，日間月票3000元',2000),
    ('每小時30元；月租2,200元',2200),('月租2,500元，每小時30元',2500),
    ('月票：2000／月',2000),('包月：2,600',2600),
    ('全日月票 $3,200（含稅）',3200),('月租費：2500.50元',2500.5),
    ('月票每月0元',0),
    ('每小時 30 元',None),('計次50元',None),('月租另洽',None),
    ('無月租，每小時30元',None),('月租每小時30元',None),
    ('定期票每季6000元',None),('定期票3個月9000元',None),
    ('月票剩餘20格',None),('月租另洽，計次50元',None),
    ('月租戶前2小時30元',None),('月租戶每日50元',None),('月租-2000元',None),
    ('月租3000元（保證金5000元）',3000),('月租3000元（押金NT$5,000）',3000),
    ('月租3000元，另收感應卡工本費5000元',3000),('月租含保證金5000元',None),
    ('月租：日間2000元、全日3500元',3500),('月票：夜間3000元、全日2000元',2000),
    ('月票：機車300元、汽車2000元',2000),('月票另洽，日間計次100元、全日最高200元',None),
    ('定期票3個月夜間9000元、全日12000元',None),
]


@pytest.mark.parametrize('text,expected',CASES)
def test_synthetic_monthly_rent_spellings_and_false_positives(text,expected):
    result=parse_monthly_rent(text)
    assert result['monthly_rent_twd']==expected
    fragment=result['monthly_rent_text']
    assert fragment in text if expected is not None else fragment is None


def test_snapshot_conversion_preserves_original_text_and_does_not_infer_districts():
    rows=[dict(CarParkID='test',CarParkName={'Zh_tw':'測試場'},TownName='北屯區',
               Address='測試地址',FareDescription='計次50元',SpecialOfferDescription='月票２，５００元',
               CarParkPosition=dict(PositionLat=24.1,PositionLon=120.7),SrcUpdateTime='2026-11-03T00:00:00+08:00')]
    lot=normalize_tdx(rows,'臺中市')[0]
    assert lot['monthly_rent_twd']==2500 and lot['monthly_rent_text']=='月票２，５００元'
    assert lot['fare_description']=='計次50元' and lot['district']=='北屯區' and lot['lat']==24.1
    del rows[0]['TownName']
    assert normalize_tdx(rows,'臺中市')[0]['district']==''


def test_regions_are_the_complete_moi_snapshot():
    regions=CLIENT.get('/regions').json()
    assert len(regions)==22 and sum(len(r['districts']) for r in regions)==368
    assert len(next(r for r in regions if r['city']=='臺中市')['districts'])==29
    assert len({r['city'] for r in regions})==22
    assert all(len(set(r['districts']))==len(r['districts']) and r['districts'] for r in regions)
    assert not any(r['city'].startswith('台') for r in regions)


@pytest.fixture
def sample_parking():
    snapshot=build_snapshot(FIXTURE)
    app.dependency_overrides[load_parking_snapshot]=lambda:snapshot
    yield snapshot
    app.dependency_overrides.pop(load_parking_snapshot,None)


def test_parking_endpoint_filters_sorts_and_computes_stats_before_limit(sample_parking):
    response=CLIENT.get('/planner/parking',params=dict(city='臺北市',district='士林區'))
    assert response.status_code==200
    body=response.json()
    assert body['supported'] and body['data_available'] and not body['source']['is_sample']
    assert all(lot['district']=='士林區' for lot in body['lots'])
    assert body['monthly_rent_stats']==dict(count=3,median=7200,minimum=7200,maximum=7500)
    lots=body['lots']
    assert lots==sorted(lots,key=lambda lot:(lot['monthly_rent_twd'] is None,lot['name']))
    large={**sample_parking,'cities':{'臺北市':{**sample_parking['cities']['臺北市'],'lots':[{**lots[0],'id':str(i),'name':str(i),'monthly_rent_twd':i} for i in range(40)]}}}
    result=parking_reference('臺北市','士林區',large)
    assert len(result['lots'])==30 and result['monthly_rent_stats']['count']==40


def test_unsupported_city_and_small_sample_never_publish_a_median(sample_parking):
    body=CLIENT.get('/planner/parking',params=dict(city='臺中市',district='北屯區')).json()
    assert body['supported'] is False and body['lots']==[]
    body=CLIENT.get('/planner/parking',params=dict(city='桃園市',district='八德區')).json()
    assert body['monthly_rent_stats']['count']==2 and body['monthly_rent_stats']['median'] is None


def test_unavailable_production_snapshot_is_not_reported_as_zero_market_supply():
    snapshot=dict(source=dict(status='available',is_sample=False,snapshot_date='2026-11-03'),cities={},unavailable=['臺中市'])
    body=parking_reference('臺中市','北屯區',snapshot)
    assert not body['supported'] and not body['data_available']
    assert body['message']=='TDX 目前沒有臺中市的路外停車場資料，請自行填寫停車費。'


def test_parking_metadata_does_not_change_any_vehicle_calculations():
    details=dict(purchase_price=849000,payment_method='cash',monthly_parking=2800)
    request=dict(start_period='2026-11',months=60,inflation_rate=.02,
                 vehicles=[dict(name='買車',purchase_period='2027-03',details=details)])
    original=CLIENT.post('/planner/vehicle-events',json=request)
    details.update(has_parking_space=False,parking_lot_id='sample-be-03')
    enriched=CLIENT.post('/planner/vehicle-events',json=request)
    assert original.status_code==enriched.status_code==200
    assert original.json()==enriched.json()
    details['has_parking_space']=True
    assert CLIENT.post('/planner/vehicle-events',json=request).json()==original.json()


def test_anonymous_only_download_never_reads_credentials(monkeypatch):
    import urllib.error
    from scripts import fetch_tdx_parking as fetch
    def denied(_):
        raise urllib.error.HTTPError(fetch.URL,401,'Unauthorized',{},None)
    def forbidden(*args,**kwargs):
        pytest.fail('anonymous-only mode must not read credentials')
    monkeypatch.setattr(fetch,'get_json',denied)
    monkeypatch.setattr(fetch.os.environ,'get',forbidden)
    with pytest.raises(ValueError,match='匿名下載遭拒'):
        fetch.download(anonymous_only=True)
