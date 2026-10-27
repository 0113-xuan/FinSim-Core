"""Small curated official-source snapshot; independent of legacy km/L catalog."""
from copy import deepcopy

CHECKED_ON = '2026-10-26'
CC = 'https://www.toyota.com.tw/showroom/COROLLA_CROSS/fullsepc.aspx'
FIT = 'https://www.honda-taiwan.com.tw/Auto/Cars/FIT'
ALTIS = 'https://www.toyota.com.tw/showroom/ALTIS/fullsepc.aspx'
TESLA = 'https://www.tesla.com/zh_tw/model3/design?redirect=no'
CC_SEATS = 'https://newcar.u-car.com.tw/Toyota/Corolla%20Cross/7183/spec'
ALTIS_SEATS = 'https://greenlifestyle.moenv.gov.tw/categories/greenProductdetailPage?product=23905&type=1'
TESLA_SPECS = 'https://www.tesla.com/zh_tw/model3-performance'


def record(id, brand, model, trim, price, body, power, efficiency, url, image_url,
           *, seats: int | None, seats_source: str | None, seats_source_type: str,
           seats_verification: str, seats_note: str):
    if seats is not None and (type(seats) is not int or not 1 <= seats <= 9 or not seats_source):
        raise ValueError('已知座位數須為 1 至 9 的整數，且必須提供來源。')
    return dict(id=id, brand=brand, model=model, trim=trim, model_year=None,
                model_year_note='官網未明示年式；以查詢日版本為準，不推定年式',
                price_twd=price, body_type=body, seats=seats, powertrain=power,
                efficiency=efficiency, efficiency_unit='km/kWh' if power == 'bev' else 'km/L',
                checked_on=CHECKED_ON, source_type='official', source_url=url,
                image_url=image_url, image_note='車系示意圖，非指定版本實車',
                sources=dict(price=url, specifications=(TESLA_SPECS if power == 'bev' else url),
                             efficiency=None if efficiency is None else url, seats=seats_source),
                source_types=dict(price='official', specifications='official', efficiency='official' if efficiency is not None else 'unknown', seats=seats_source_type),
                verification=dict(price='indexed_only' if power == 'bev' else 'verified',
                                  specifications='indexed_only' if power == 'bev' else 'verified',
                                  efficiency='unverified' if efficiency is None else 'verified',
                                  seats='unverified' if seats is None else seats_verification, model_year='unverified'),
                verification_notes=dict(seats=seats_note,
                                        price='本次訂購頁未回傳可讀售價，僅官方搜尋索引佐證，現行售價待確認' if power == 'bev' else '本次已讀取官方規格表核對版本與價格',
                                        model_year='查詢日及型錄生產適用月份不等於車型年式'),
                limitations=['官方測試油耗不等於實際道路油耗', '保險、稅費、保養採規劃預算，非車款報價'] if power != 'bev'
                else ['未取得此版本可核對的台灣官方電耗，不計算完整成本排名', '充電損耗、安裝費與未來電車稅制未建模'])


CATALOG = [
    record('cc-gas-luxury', 'Toyota', 'Corolla Cross', '豪華', 809000, 'suv', 'ice', 14.3, CC, None,
           seats=5, seats_source=CC_SEATS, seats_source_type='third_party', seats_verification='indexed_only', seats_note='U-CAR 對應版本搜尋索引顯示 5 人；直連 403，尚未完成官方逐版座位核對'),
    record('cc-hev-luxury', 'Toyota', 'Corolla Cross', 'HYBRID 豪華', 849000, 'suv', 'hev', 23.5, CC, None,
           seats=5, seats_source=CC_SEATS, seats_source_type='third_party', seats_verification='indexed_only', seats_note='U-CAR 對應版本搜尋索引顯示 5 人；直連 403，尚未完成官方逐版座位核對'),
    record('cc-hev-flagship', 'Toyota', 'Corolla Cross', 'HYBRID 旗艦', 989000, 'suv', 'hev', 23.5, CC, None,
           seats=5, seats_source=CC_SEATS, seats_source_type='third_party', seats_verification='indexed_only', seats_note='U-CAR 對應版本搜尋索引顯示 5 人；直連 403，尚未完成官方逐版座位核對'),
    record('fit-home', 'Honda', 'FIT', 'HOME 汽油版', 759000, 'hatchback', 'ice', 17.9, FIT, None,
           seats=5, seats_source=FIT, seats_source_type='official', seats_verification='verified', seats_note='Honda 規配表：全車五席 3 點式 ELR 安全帶，HOME 欄標示配備'),
    record('fit-hev', 'Honda', 'FIT', 'e:HEV 油電版', 829000, 'hatchback', 'hev', 26.9, FIT, None,
           seats=5, seats_source=FIT, seats_source_type='official', seats_verification='verified', seats_note='Honda 規配表：全車五席 3 點式 ELR 安全帶，e:HEV 欄標示配備'),
    record('altis-classic', 'Toyota', 'Corolla Altis', '經典', 735000, 'sedan', 'ice', 15.7, ALTIS, None,
           seats=5, seats_source=ALTIS_SEATS, seats_source_type='government', seats_verification='indexed_only', seats_note='環境部同車系 1798c.c. CVT 4D 產品索引顯示 5 人；頁面需 JavaScript，指定年式版本待確認'),
    record('model3-lr-rwd', 'Tesla', 'Model 3', 'Long Range 後輪驅動', 1749900, 'sedan', 'bev', None, TESLA, None,
           seats=5, seats_source=TESLA_SPECS, seats_source_type='official', seats_verification='indexed_only', seats_note='Tesla 台灣 LR 後驅規格搜尋索引列 5 個座椅；直連改版後未回傳完整表格，待重新核對'),
]


def recommendation_catalog():
    return deepcopy(CATALOG)
