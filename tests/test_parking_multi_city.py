import json
from pathlib import Path
import urllib.error

import pytest
from fastapi.testclient import TestClient

from app.parking import (CITY_CODES, load_regions, load_parking_snapshot, normalize_tdx,
                         parse_monthly_rent, resolve_district)
from main import app
from scripts import fetch_tdx_parking as fetch

# The first 19 excerpts are task cases from the supplied TDX raw set (2026-11-03).
# Named Taipei regressions are also real; the final billing probes combine these
# rates synthetically to distinguish required billing from separate alternatives.
REAL_CASES=[
 ('臺北-健康國小B1停車場','汽車季繳:9,300元/月、汽車月繳:3,300元/月、汽車臨停15元/半小時',3300),
 ('臺北-Times昆陽街','汽車臨停30元/半小時，平日最高收費230元，假日無上限\n汽車3,500元/月',3500),
 ('臺北-達賢圖書館收費停車場','月租車輛：全日票每月2000元，公車全日票每月3431元。機車免收停車費',2000),
 ('桃園-八德區永福停車場','計時:每小時20元當日最高100元月租2000元',2000),
 ('桃園-大江公有停車場','計時每小時20園前12小時80元月租1200元季繳3000元',1200),
 ('桃園-文德公園停車場','計時:20/時。進場24小時收費60元 月租:4500/季繳',None),
 ('桃園-廣豐二停車場','小型車臨停計時30元/時 小型車全日月租每月3600元。',3600),
 ('彰化-城市車旅員林惠明站','臨停:第一小時20元，爾後半小時計 當日最高70 月租:1000/月',1000),
 ('嘉義縣-強展金世界停車場','20元/時。1500元/月',1500),
 ('嘉義縣-新港停一立體停車場','60元/時、2,400元/月',2400),
 ('花蓮-市八十三街停車場','年繳:20000元、半年繳:11000元、月繳:2000元',2000),
 ('花蓮-國富二街停車場','月繳$2500/月、季繳$2200/月、年繳$2000/月',2500),
 ('花蓮-彪吉利停場車','平／假日一小時$25(月租一個月$500)',500),
 ('高雄-俥亭前鎮民權二停車場','每半小時50元(當日連續停放最高上限收費500元) 月租收每月4,000元。',4000),
 ('高雄-嘟嘟房三民民族站停車場','每半小時50元(當日連續停放最高收費500元)。月租收費；每月5,000元。',5000),
 ('苗栗-中興停車場','20元/時(08-20) 月租2400元/月',2400),
 ('苗栗-文強竹南國中地下停車場','小型車每小時20元，機車每小時10元。 小型車每月1,800元，機車每月370元。',1800),
 ('屏東-幸福公園停車場','計時:20/小時 月租:1800/月',1800),
 ('臺東-長濱鄉壹號停車場','8000/一年，4000/半年，667/月。',667),
 ('臺北-TPE1823嘟嘟房北投文林站','汽車5,000元/月(需季繳)',None),
 ('臺北-TPE0843大湖活動中心暨溫水游泳池','月租1,500元、季繳',None),
 ('臺北-TPE0131華中橋堤外停車場','月租2400元/月，以3個月為一季繳納，半年繳費者14000元',None),
 ('分開標價的月季方案','月租1200元季繳3000元',1200),
 ('月繳後的可選季繳優惠','月繳3000元，亦可季繳享優惠',3000),
 ('明示必須季繳的完整總額','月租5000元/月（需季繳15000元）',None),
 ('月租後要求三個月季繳','月租2000元，季繳3個月',None),
]


@pytest.mark.parametrize('name,text,expected',REAL_CASES,ids=[case[0] for case in REAL_CASES])
def test_real_tdx_wordings(name,text,expected):
    result=parse_monthly_rent(text)
    assert result['monthly_rent_twd']==expected
    if expected is not None:
        assert result['monthly_rent_text'] in text


@pytest.mark.parametrize('city,town,address,name,expected',[
 ('臺北市','士林區','臺北市信義區信義路','停車場',('士林區','town_name')),
 ('臺北市','','臺北市士林區中山路','停車場',('士林區','address')),
 ('臺北市','','台北市士林區中山路','停車場',('士林區','address')),
 ('桃園市','','桃園市永福路','八德區永福停車場',('八德區','name')),
 ('臺北市','','新北市板橋區中山路','停車場',('','none')),
 ('新竹市','','臺南市東區中山路','停車場',('','none')),
 ('臺北市','','中山路一號','停車場',('','none')),
])
def test_official_district_matching(city,town,address,name,expected):
    assert resolve_district(city,town,address,name)==expected


def test_deduplicate_only_identical_ids_within_each_city():
    row=dict(CarParkID='same',CarParkName={'Zh_tw':'士林停車場'},Address='臺北市士林區',FareDescription='月租3000元')
    lots=normalize_tdx([row,{**row,'FareDescription':'月租4000元'},{**row,'CarParkID':'other'}],'臺北市')
    assert len(lots)==2 and lots[0]['monthly_rent_twd']==3000


def test_offline_directory_conversion_does_not_read_secrets_or_use_network(tmp_path,monkeypatch):
    fixture=Path(__file__).parent/'fixtures/parking/multi_city'
    def forbidden(*args,**kwargs):pytest.fail('offline conversion attempted network')
    monkeypatch.setattr(fetch,'get_json',forbidden)
    monkeypatch.setattr(fetch,'download',forbidden)
    monkeypatch.setattr(fetch,'ROOT',tmp_path)
    monkeypatch.setattr(fetch.sys,'argv',['fetch_tdx_parking.py','--from-dir',str(fixture)])
    (tmp_path/'data/parking').mkdir(parents=True)
    assert fetch.main()==0
    data=json.loads((tmp_path/'data/parking/tw_carparks.json').read_text(encoding='utf-8'))
    assert set(data['cities'])=={'臺北市','桃園市'}
    assert data['source']['snapshot_date']=='2026-11-03'


def test_429_waits_then_retries_without_network(monkeypatch):
    waits=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):return None
        def read(self):return b'{"CarParks":[]}'
    attempts=[]
    def limited(*args,**kwargs):
        attempts.append(1)
        if len(attempts)==1:raise urllib.error.HTTPError('https://example.invalid',429,'limited',{'Retry-After':'5'},None)
        return Response()
    monkeypatch.setattr(fetch.urllib.request,'urlopen',limited)
    monkeypatch.setattr(fetch.time,'sleep',waits.append)
    assert fetch.get_json('unused')=={'CarParks':[]}
    assert waits==[5] and len(attempts)==2


def test_real_snapshot_integrity_and_api_coverage():
    snapshot=load_parking_snapshot()
    assert len(snapshot['cities'])==19
    assert set(snapshot['unavailable'])=={'臺中市','新北市','基隆市'}
    assert set(CITY_CODES.values())=={r['city'] for r in load_regions()}
    for city,entry in snapshot['cities'].items():
        assert len({l['id'] for l in entry['lots']})==len(entry['lots'])==entry['coverage']['total']
        valid=next(r['districts'] for r in load_regions() if r['city']==city)
        assert all(l['district'] in valid or l['district']=='' for l in entry['lots'])
    client=TestClient(app)
    body=client.get('/planner/parking',params=dict(city='臺北市',district='士林區')).json()
    assert body['supported'] and body['lots'] and body['coverage']['total']==673
    assert body['coverage']['with_monthly_rent']==88
    assert body['lots'][0]['monthly_rent_twd'] is not None
    for city in ['臺中市','不存在的縣市']:
        body=client.get('/planner/parking',params=dict(city=city,district='北屯區')).json()
        assert body['supported'] is False
        assert body['message']==f'TDX 目前沒有{city}的路外停車場資料，請自行填寫停車費。'
    body=client.get('/planner/parking',params=dict(city='臺北市',district='不存在')).json()
    assert body['message']=='不存在在 TDX 資料中沒有可對應的停車場，請自行填寫停車費。'
