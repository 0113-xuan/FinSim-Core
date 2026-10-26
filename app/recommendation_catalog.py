"""Small curated official-source snapshot; independent of legacy km/L catalog."""
from copy import deepcopy

CHECKED_ON = '2026-10-26'
CC = 'https://www.toyota.com.tw/showroom/COROLLA_CROSS/fullsepc.aspx'
FIT = 'https://www.honda-taiwan.com.tw/Auto/Cars/FIT'
ALTIS = 'https://www.toyota.com.tw/showroom/ALTIS/'
TESLA = 'https://www.tesla.com/zh_tw/model3/design?redirect=no'


def record(id, brand, model, trim, price, body, power, efficiency, url, image_url):
    return dict(id=id, brand=brand, model=model, trim=trim, model_year=None,
                model_year_note='官網未明示年式；以查詢日版本為準，不推定年式',
                price_twd=price, body_type=body, seats=5, powertrain=power,
                efficiency=efficiency, efficiency_unit='km/kWh' if power == 'bev' else 'km/L',
                checked_on=CHECKED_ON, source_type='official', source_url=url,
                image_url=image_url, image_note='車系示意圖，非指定版本實車',
                sources=dict(price=url, specifications=('https://www.tesla.com/zh_tw/model3-performance' if power == 'bev' else url),
                             efficiency=None if efficiency is None else url),
                limitations=['官方測試油耗不等於實際道路油耗', '保險、稅費、保養採規劃預算，非車款報價'] if power != 'bev'
                else ['未取得此版本可核對的台灣官方電耗，不計算完整成本排名', '充電損耗、安裝費與未來電車稅制未建模'])


# Image links are official public model images, not downloaded copies.
CATALOG = [
    record('cc-gas-luxury', 'Toyota', 'Corolla Cross', '汽油豪華', 809000, 'suv', 'ice', 14.3, CC, None),
    record('cc-hev-luxury', 'Toyota', 'Corolla Cross', 'HYBRID 豪華', 849000, 'suv', 'hev', 23.5, CC, None),
    record('cc-hev-flagship', 'Toyota', 'Corolla Cross', 'HYBRID 旗艦', 989000, 'suv', 'hev', 23.5, CC, None),
    record('fit-home', 'Honda', 'FIT', 'HOME 汽油版', 759000, 'hatchback', 'ice', 17.9, FIT, None),
    record('fit-hev', 'Honda', 'FIT', 'e:HEV 油電版', 829000, 'hatchback', 'hev', 26.9, FIT, None),
    record('altis-classic', 'Toyota', 'Corolla Altis', '汽油經典', 735000, 'sedan', 'ice', 15.7, ALTIS, None),
    record('model3-lr-rwd', 'Tesla', 'Model 3', 'Long Range 後輪驅動', 1749900, 'sedan', 'bev', None, TESLA, None),
]


def recommendation_catalog():
    return deepcopy(CATALOG)
