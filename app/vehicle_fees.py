"""Offline reference snapshots for privately owned passenger cars, checked 2026-11-02.

Road fees: attachment 2, private passenger car / annual columns (not bus or
commercial columns). Blank cells, including <=250 and >8000 cc, stay unknown.
Toyota's calculator is only a cross-check: 1798 cc = 7120 + 4800 annually;
its additional 1250 registration charge is not included here.
"""
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite

CHECKED_ON = '2026-11-02'
LICENSE_SOURCE = dict(name='財政部稅務入口網：認識使用牌照稅',
    url='https://www.etax.nat.gov.tw/etwmain/tax-info/understanding/tax-saving-manual/local/vehicle-license-tax/2Jv5NBY',
    updated_on='2026-04-09', checked_on=CHECKED_ON)
ROAD_SOURCE = dict(name='公路使用養護安全管理費徵收及分配辦法：附表二',
    url='https://law.moj.gov.tw/LawClass/LawGetFile.ashx?FileId=0000418377&lan=C',
    regulation_url='https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=K0040007',
    updated_on='2026-05-21', checked_on=CHECKED_ON)
COMPULSORY_SOURCE = dict(name='金管會強制汽車責任保險費率表（汽車三，自用小客車）',
    url='https://law.fsc.gov.tw/LawContent.aspx?id=FL006900',
    table_url='https://law.fsc.gov.tw/Download.ashx?FileID=23511&id=FL006900&type=LAW',
    updated_on='2024-04-17', checked_on=CHECKED_ON)
VOLUNTARY_SOURCE = dict(name='UpToGo：公開投保範例原價與網路價（非報價）',
    url='https://uptogo.com.tw/汽機車/汽車保險一年大概多少錢？/', checked_on=CHECKED_ON)
BODY_SOURCE = dict(name='Finfo：Toyota 車系甲乙丙式車體險價格比較，Altis 79.9 萬範例',
    url='https://finfo.tw/blog/insurance-vehicle/toyota-車系甲乙丙式車體險價格比較-altis-corolla-corona-sienta-yaris',
    updated_on='2025-07-10', checked_on=CHECKED_ON)

LICENSE_TAX_BANDS = ((1,500,1620),(501,600,2160),(601,1200,4320),
    (1201,1800,7120),(1801,2400,11230),(2401,3000,15210),
    (3001,4200,28220),(4201,5400,46170),(5401,6600,69690),
    (6601,7800,117000),(7801,None,151200))
ROAD_FEE_BANDS = ((251,500,2160,1296),(501,600,2880,1728),(601,1200,4320,2592),
    (1201,1800,4800,2880),(1801,2400,6180,3708),(2401,3000,7200,4320),
    (3001,3600,8640,5184),(3601,4200,9810,5886),(4201,4800,11220,6732),
    (4801,5400,12180,7308),(5401,6000,13080,7848),(6001,6600,13950,8370),
    (6601,7200,14910,8946),(7201,8000,15720,9432))
# Official first-time / grade 4 premiums. No driver demographics are collected.
FIRST_TIME_GRADE_4 = (
    dict(age='20歲（含）以下', male=2893, female=2056),
    dict(age='超過20歲至25歲（含）', male=2694, female=1926),
    dict(age='超過25歲至30歲（含）', male=1866, female=1457),
    dict(age='超過30歲至60歲（含）', male=1398, female=1318),
    dict(age='超過60歲', male=1448, female=1188),
)
INSURANCE_IDS = ('compulsory','third_party','excess_liability','body_a','body_b','body_c','theft')


def annual_vehicle_tax(displacement_cc, fuel_type):
    if fuel_type not in ('gasoline','hybrid','diesel','ev'):
        raise ValueError('燃料種類請選汽油、油電混合、柴油或純電')
    if (isinstance(displacement_cc, bool) or not isinstance(displacement_cc, (int, float))
            or not isfinite(displacement_cc) or int(displacement_cc) != displacement_cc
            or displacement_cc < 0 or (fuel_type != 'ev' and displacement_cc == 0)):
        raise ValueError('排氣量須為正整數；純電車可填 0')
    sources = dict(license_tax={**LICENSE_SOURCE}, road_fee={**ROAD_SOURCE})
    if fuel_type == 'ev':
        return dict(license_tax=0,road_fee=0,total=0,sources=sources,notes=[
            '純電車使用牌照稅免徵至 2030-12-31；期限後須重新確認，這不是永久免稅。',
            '純電車目前不收公路養管費；交通部規劃未來對電動車徵收，最快約 2030 年（尚非已生效費額）。'])
    license_tax = next(amount for low, high, amount in LICENSE_TAX_BANDS
                       if displacement_cc >= low and (high is None or displacement_cc <= high))
    road_fee = next((diesel if fuel_type == 'diesel' else gas
                     for low, high, gas, diesel in ROAD_FEE_BANDS if low <= displacement_cc <= high), None)
    notes = ['自用小客車全年費額；油電混合與汽油車適用相同級距。']
    if road_fee is None:
        notes.append('查無官方費額，請手動填寫')
    return dict(license_tax=license_tax,road_fee=road_fee,
                total=None if road_fee is None else license_tax+road_fee,notes=notes,sources=sources)


def insurance_reference(purchase_price):
    price = Decimal(str(purchase_price))
    if not price.is_finite() or price <= 0:
        raise ValueError('車價須為大於零的有效金額')
    def item(id, name, description, low, high, default, source):
        return dict(id=id,name=name,description=description,required=id=='compulsory',
                    low=low,high=high,default=default,source={**source})
    rows = [item('compulsory','強制汽車責任保險',
        '依法必保。首次投保第4級；預設以超過30至60歲男性1,398元作預算，女性為1,318元；其他年齡保費不同，非個人報價。',
        1188,2893,1398,COMPULSORY_SOURCE),
        item('third_party','第三人責任險','對他人體傷200萬／事故400萬、財損50萬的公開範例；預設採原價作預算。',3858,6430,6430,VOLUNTARY_SOURCE),
        item('excess_liability','超額責任險','每一事故1,000萬的公開範例；承保條件與基本責任險須以報價確認。',1188,1320,1320,VOLUNTARY_SOURCE)]
    for id,name,ratio in [('body_a','甲式車體損失險','0.052'),('body_b','乙式車體損失險','0.029'),('body_c','丙式車體損失險','0.012')]:
        amount = int((price*Decimal(ratio)/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP)*100)
        rows.append(item(id,name,f'依單一範例車款的比例估算（車價的{float(ratio)*100:g}%），四捨五入至百元；不是保險公司報價。',amount,amount,amount,BODY_SOURCE))
    rows.append(item('theft','竊盜損失險','自負額10%的公開範例；預設採原價作預算。',1705,1894,1894,VOLUNTARY_SOURCE))
    return rows
