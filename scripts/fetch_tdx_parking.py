"""Build a multi-city parking snapshot offline or via rate-limited downloads.

--from-dir never accesses TDX or credentials. The supplied raw set was downloaded
on 2026-11-03; use --snapshot-date for later offline sets without dated metadata.
"""
import argparse
from datetime import date, datetime, timezone, timedelta
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.parking import CITY_CODES, MONTHLY, is_scooter_only, normalize_tdx

URL = 'https://tdx.transportdata.tw/api/basic/v1/Parking/OffStreet/CarPark/City/{city}?$format=JSON'
TOKEN_URL = 'https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token'


def get_json(request):
    """Retry rate limiting without logging HTTP bodies, headers or secrets."""
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request,timeout=60) as response:
                return json.loads(response.read().decode('utf-8-sig'))
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 3:
                raise
            retry=error.headers.get('Retry-After','') if error.headers else ''
            delay=min(60,max(3,float(retry))) if retry.isdigit() else 3*2**attempt
            time.sleep(delay)


def download(city='Taipei', anonymous_only=False, token_cache=None):
    cache=token_cache if token_cache is not None else {}
    headers={'Accept':'application/json'}
    if cache.get('token'):
        headers['Authorization']='Bearer '+cache['token']
    try:
        return get_json(urllib.request.Request(URL.format(city=city),headers=headers))
    except urllib.error.HTTPError as error:
        if error.code not in (401,403):
            raise ValueError(f'TDX 下載失敗（HTTP {error.code}），未修改整合快照') from None
    if anonymous_only:
        raise ValueError('匿名下載遭拒，需註冊 TDX 後以環境變數提供憑證；未修改快照')
    client_id,secret=os.environ.get('TDX_CLIENT_ID'),os.environ.get('TDX_CLIENT_SECRET')
    if not client_id or not secret:
        raise ValueError('請設定 TDX_CLIENT_ID、TDX_CLIENT_SECRET 環境變數，或使用 --from-dir 離線轉換')
    encoded=urllib.parse.urlencode(dict(grant_type='client_credentials',client_id=client_id,client_secret=secret)).encode()
    token=get_json(urllib.request.Request(TOKEN_URL,data=encoded,
        headers={'Content-Type':'application/x-www-form-urlencoded'})).get('access_token')
    if not token:
        raise ValueError('TDX 未提供存取權杖，未修改快照')
    cache['token']=token
    return get_json(urllib.request.Request(URL.format(city=city),headers={'Authorization':'Bearer '+token,'Accept':'application/json'}))


def build_snapshot(folder, snapshot_date='2026-11-03'):
    """Convert known City files; explicit zero replies denote unavailable cities."""
    folder=Path(folder)
    summary_path=folder/'_download_summary.json'
    summary=json.loads(summary_path.read_text(encoding='utf-8-sig')) if summary_path.exists() else {}
    counts=summary.get('counts',summary)
    snapshot_date=summary.get('snapshot_date',snapshot_date)
    date.fromisoformat(snapshot_date)
    cities,unavailable={},[]
    for code,city in CITY_CODES.items():
        path=folder/f'{code}.json'
        if not path.exists():
            if counts.get(code,0)>0:
                raise ValueError(f'{code} 的原始檔遺失，未修改整合快照')
            if code in counts:
                unavailable.append(city)
            continue
        payload=json.loads(path.read_text(encoding='utf-8-sig'))
        rows=payload if isinstance(payload,list) else payload['CarParks']
        if not rows:
            unavailable.append(city)
            continue
        normalized=normalize_tdx(payload,city)
        lots=[lot for lot in normalized if not is_scooter_only(lot['name'])]
        coverage=dict(total=len(lots),with_district=sum(bool(l['district']) for l in lots),
                      with_monthly_rent=sum(l['monthly_rent_twd'] is not None for l in lots))
        related=[l for l in lots if MONTHLY.search(l['fare_description']+'；'+l['special_offer_description'])]
        cities[city]=dict(tdx_city=code,coverage=coverage,duplicates_removed=len(rows)-len(normalized),
                          excluded_scooter_only=len(normalized)-len(lots),
                          monthly_related_count=len(related),
                          unparsed_monthly_count=sum(l['monthly_rent_twd'] is None for l in related),lots=lots)
    if not cities:
        raise ValueError('資料夾沒有可轉換的縣市停車場，未修改整合快照')
    source=dict(name='交通部 TDX 各縣市路外停車場靜態資料',url='https://tdx.transportdata.tw/',api_url_template=URL,
        license='政府資料開放授權條款－第1版',license_url='https://data.gov.tw/license',
        snapshot_date=snapshot_date,status='available',is_sample=False)
    return dict(source=source,cities=cities,unavailable=unavailable)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-dir',type=Path,help='只讀本機原始檔，不連網、不讀憑證')
    parser.add_argument('--snapshot-date',default='2026-11-03',help='離線下載日期 YYYY-MM-DD')
    parser.add_argument('--anonymous-only',action='store_true',help='不使用憑證環境變數')
    parser.add_argument('--interval',type=float,default=3,help='縣市下載間隔，至少 3 秒')
    args=parser.parse_args()
    try:
        folder=args.from_dir
        if folder is None:
            folder=ROOT/'data/parking/raw/tdx';folder.mkdir(parents=True,exist_ok=True)
            counts,cache={},{}
            for index,code in enumerate(CITY_CODES):
                if index:
                    time.sleep(max(3,args.interval))
                payload=download(code,args.anonymous_only,cache)
                rows=payload if isinstance(payload,list) else payload['CarParks']
                counts[code]=len(rows)
                # Empty replies must supersede stale nonempty city files too.
                (folder/f'{code}.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            today=str(datetime.now(timezone(timedelta(hours=8))).date())
            (folder/'_download_summary.json').write_text(json.dumps(dict(snapshot_date=today,counts=counts),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        snapshot=build_snapshot(folder,args.snapshot_date)
        output=ROOT/'data/parking/tw_carparks.json'
        output.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f"整合快照：{len(snapshot['cities'])} 縣市、{sum(c['coverage']['total'] for c in snapshot['cities'].values())} 間停車場；日期 {snapshot['source']['snapshot_date']}。請重啟服務以載入快照。")
    except Exception as error:
        message=str(error) if isinstance(error,ValueError) and not isinstance(error,json.JSONDecodeError) else '下載或轉換失敗，請檢查連線與原始資料；未更新整合快照'
        print(message,file=sys.stderr);return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
