"""Download one Taichung TDX snapshot. Credentials come ONLY from process env."""
import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.parking import normalize_tdx

URL = 'https://tdx.transportdata.tw/api/basic/v1/Parking/OffStreet/CarPark/City/Taichung?$format=JSON'
TOKEN_URL = 'https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token'


def get_json(request):
    with urllib.request.urlopen(request,timeout=60) as response:
        return json.loads(response.read().decode('utf-8-sig'))


def download(anonymous_only=False):
    try:
        return get_json(urllib.request.Request(URL,headers={'Accept':'application/json'}))
    except urllib.error.HTTPError as error:
        if error.code not in (401,403):
            raise ValueError(f'TDX 下載失敗（HTTP {error.code}），未修改快照') from None
    if anonymous_only:
        raise ValueError('匿名下載遭拒，需註冊 TDX 後以環境變數提供憑證；未修改快照')
    client_id, secret = os.environ.get('TDX_CLIENT_ID'), os.environ.get('TDX_CLIENT_SECRET')
    if not client_id or not secret:
        raise ValueError('需要使用者註冊 TDX 並設定 TDX_CLIENT_ID、TDX_CLIENT_SECRET 環境變數，再執行 script；未修改快照')
    encoded = urllib.parse.urlencode(dict(grant_type='client_credentials',client_id=client_id,client_secret=secret)).encode()
    token = get_json(urllib.request.Request(TOKEN_URL,data=encoded,
        headers={'Content-Type':'application/x-www-form-urlencoded'})).get('access_token')
    if not token:
        raise ValueError('TDX 未提供存取權杖，未修改快照')
    return get_json(urllib.request.Request(URL,headers={'Authorization':'Bearer '+token,'Accept':'application/json'}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--anonymous-only',action='store_true',help='只試匿名下載，不讀取憑證環境變數')
    parser.add_argument('--from-file',type=Path,help='從已下載的 TDX 原始 JSON 轉換，不連網')
    args=parser.parse_args()
    try:
        payload=json.loads(args.from_file.read_text(encoding='utf-8-sig')) if args.from_file else download(args.anonymous_only)
        lots=normalize_tdx(payload)
        today=str(datetime.now(timezone(timedelta(hours=8))).date())
        source=dict(name='交通部 TDX 臺中市路外停車場靜態資料',url=URL,
            license='政府資料開放授權條款－第1版',license_url='https://data.gov.tw/license',
            snapshot_date=today,status='available',is_sample=False)
        folder=ROOT/'data/parking';(folder/'raw').mkdir(parents=True,exist_ok=True)
        (folder/'raw/taichung_carparks.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (folder/'taichung_carparks.json').write_text(json.dumps(dict(source=source,lots=lots),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f"已下載 {len(lots)} 間停車場；{sum(lot['monthly_rent_twd'] is not None for lot in lots)} 間可解析月租，{sum(not lot['district'] for lot in lots)} 間缺少 TownName；快照日期 {today}。請重啟服務以重新載入快照。")
    except Exception as error:
        # Never echo an HTTP body, request object, headers, token or credentials.
        message=str(error) if isinstance(error,ValueError) and not isinstance(error,json.JSONDecodeError) else 'TDX 下載或轉換失敗，請檢查連線、憑證與原始資料；未更新快照'
        print(message,file=sys.stderr);return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
