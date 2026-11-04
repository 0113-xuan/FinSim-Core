"""Official Taiwan catalog snapshots; prices and test efficiency are not live quotes."""
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


TOYOTA_SOURCE = 'https://www.toyota.com.tw/showroom/COROLLA_CROSS/fullsepc.aspx'
HONDA_SOURCE = 'https://www.honda-taiwan.com.tw/Auto/Calculator'
CATALOG = [
    dict(id='toyota-cross-gas-luxury', brand='Toyota', model='Corolla Cross', trim='汽油豪華', price_twd=809000, efficiency_km_l=14.3, source_url=TOYOTA_SOURCE, source_period='2026-11', checked_on='2026-11-04', displacement_cc=1798, fuel_type='gasoline', spec_source=TOYOTA_SOURCE),
    dict(id='toyota-cross-hybrid-luxury', brand='Toyota', model='Corolla Cross', trim='HYBRID 豪華', price_twd=849000, efficiency_km_l=23.5, source_url=TOYOTA_SOURCE, source_period='2026-11', checked_on='2026-11-04', displacement_cc=1798, fuel_type='hybrid', spec_source=TOYOTA_SOURCE),
    dict(id='toyota-cross-hybrid-flagship', brand='Toyota', model='Corolla Cross', trim='HYBRID 旗艦', price_twd=989000, efficiency_km_l=23.5, source_url=TOYOTA_SOURCE, source_period='2026-11', checked_on='2026-11-04', displacement_cc=1798, fuel_type='hybrid', spec_source=TOYOTA_SOURCE),
    dict(id='honda-hrv-hybrid-s', brand='Honda', model='HR-V', trim='e:HEV S', price_twd=899000, efficiency_km_l=23.5, source_url=HONDA_SOURCE, source_period='2026-11', checked_on='2026-11-04', displacement_cc=1498, fuel_type='hybrid', spec_source='https://www.honda-taiwan.com.tw/HRV/'),
    dict(id='honda-hrv-hybrid-prestige', brand='Honda', model='HR-V', trim='e:HEV Prestige', price_twd=959000, efficiency_km_l=23.5, source_url=HONDA_SOURCE, source_period='2026-11', checked_on='2026-11-04', displacement_cc=1498, fuel_type='hybrid', spec_source='https://www.honda-taiwan.com.tw/HRV/'),
    dict(id='toyota-yaris-cross-gas', brand='Toyota', model='YARiS CROSS', trim='享樂版', price_twd=695000, efficiency_km_l=17.5, source_url='https://www.toyota.com.tw/showroom/YARISCROSS/fullsepc.aspx', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1496, fuel_type='gasoline', spec_source='https://www.toyota.com.tw/showroom/YARISCROSS/fullsepc.aspx', category='mainstream'),
    dict(id='toyota-altis-classic', brand='Toyota', model='Corolla Altis', trim='經典', price_twd=735000, efficiency_km_l=15.7, source_url='https://www.toyota.com.tw/showroom/ALTIS/fullsepc.aspx', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1798, fuel_type='gasoline', spec_source='https://www.toyota.com.tw/showroom/ALTIS/fullsepc.aspx', category='mainstream'),
    dict(id='toyota-altis-hybrid-luxury', brand='Toyota', model='Corolla Altis', trim='HYBRID 豪華', price_twd=855000, efficiency_km_l=25.3, source_url='https://www.toyota.com.tw/showroom/ALTIS/fullsepc.aspx', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1798, fuel_type='hybrid', spec_source='https://www.toyota.com.tw/showroom/ALTIS/fullsepc.aspx', category='mainstream'),
    dict(id='toyota-rav4-hybrid-luxury', brand='Toyota', model='RAV4', trim='豪華', price_twd=1040000, efficiency_km_l=24.0, source_url='https://www.toyota.com.tw/showroom/RAV4/fullsepc.aspx', source_period='2026-11', checked_on='2026-11-04', displacement_cc=2487, fuel_type='hybrid', spec_source='https://www.toyota.com.tw/showroom/RAV4/fullsepc.aspx', category='mainstream'),
    dict(id='toyota-camry-prestige', brand='Toyota', model='Camry', trim='尊爵', price_twd=1009000, efficiency_km_l=16.3, source_url='https://www.toyota.com.tw/showroom/CAMRY/fullsepc.aspx', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1987, fuel_type='gasoline', spec_source='https://www.toyota.com.tw/showroom/CAMRY/fullsepc.aspx', category='mainstream'),
    dict(id='toyota-camry-hybrid-prestige', brand='Toyota', model='Camry', trim='HYBRID 尊爵', price_twd=1129000, efficiency_km_l=25.3, source_url='https://www.toyota.com.tw/showroom/CAMRY/fullsepc.aspx', source_period='2026-11', checked_on='2026-11-04', displacement_cc=2487, fuel_type='hybrid', spec_source='https://www.toyota.com.tw/showroom/CAMRY/fullsepc.aspx', category='mainstream'),
    dict(id='honda-crv-vtis', brand='Honda', model='CR-V', trim='VTi-S', price_twd=999000, efficiency_km_l=15.0, source_url='https://www.honda-taiwan.com.tw/Auto/Calculator', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1498, fuel_type='gasoline', spec_source='https://www.honda-taiwan.com.tw/2026CR-V/file/Honda_CR-V_Catalogue.pdf', category='mainstream'),
    dict(id='honda-crv-hybrid-s', brand='Honda', model='CR-V', trim='e:HEV S', price_twd=1229000, efficiency_km_l=20.5, source_url='https://www.honda-taiwan.com.tw/Auto/Calculator', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1993, fuel_type='hybrid', spec_source='https://www.honda-taiwan.com.tw/2026CR-V/file/Honda_CR-V_Catalogue.pdf', category='mainstream'),
    dict(id='honda-civic-hybrid', brand='Honda', model='Civic', trim='e:HEV', price_twd=1279000, efficiency_km_l=23.7, source_url='https://www.honda-taiwan.com.tw/Auto/Calculator', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1993, fuel_type='hybrid', spec_source='https://www.honda-taiwan.com.tw/2025CIVIC/index/file/CIVIC.pdf', category='mainstream'),
    dict(id='honda-zrv-hybrid', brand='Honda', model='ZR-V', trim='e:HEV', price_twd=1199000, efficiency_km_l=20.4, source_url='https://www.honda-taiwan.com.tw/Auto/Calculator', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1993, fuel_type='hybrid', spec_source='https://www.honda-taiwan.com.tw/2026zr-v/pdf/HondaZRV.pdf', category='mainstream'),
    dict(id='toyota-vios-classic', brand='Toyota', model='Vios', trim='經典', price_twd=609000, efficiency_km_l=17.3, source_url='https://www.toyota.com.tw/showroom/VIOS/fullsepc.aspx', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1496, fuel_type='gasoline', spec_source='https://www.toyota.com.tw/showroom/VIOS/fullsepc.aspx', category='entry'),
    dict(id='honda-fit-home', brand='Honda', model='FIT', trim='HOME 汽油版', price_twd=759000, efficiency_km_l=17.9, source_url='https://www.honda-taiwan.com.tw/Auto/Cars/FIT', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1498, fuel_type='gasoline', spec_source='https://www.honda-taiwan.com.tw/Auto/Cars/FIT', category='entry'),
    dict(id='honda-fit-hybrid', brand='Honda', model='FIT', trim='e:HEV 油電版', price_twd=829000, efficiency_km_l=26.9, source_url='https://www.honda-taiwan.com.tw/Auto/Cars/FIT', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1498, fuel_type='hybrid', spec_source='https://www.honda-taiwan.com.tw/Auto/Cars/FIT', category='entry'),
    dict(id='kia-picanto-trendy', brand='Kia', model='Picanto', trim='Trendy', price_twd=599000, efficiency_km_l=18.0, source_url='https://www.kia.com/tw/showroom/picanto/features.html', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1197, fuel_type='gasoline', spec_source='https://www.kia.com/tw/showroom/picanto/specification.html', category='entry'),
    dict(id='kia-picanto-apex', brand='Kia', model='Picanto', trim='Apex', price_twd=679000, efficiency_km_l=18.0, source_url='https://www.kia.com/tw/showroom/picanto/features.html', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1197, fuel_type='gasoline', spec_source='https://www.kia.com/tw/showroom/picanto/specification.html', category='entry'),
    dict(id='toyota-bz4x', brand='Toyota', model='bZ4X', trim='bZ4X', price_twd=1280000, efficiency_km_l=None, source_url='https://www.toyota.com.tw/showroom/bZ4X/fullsepc.aspx', source_period='2026-11', checked_on='2026-11-04', displacement_cc=0, fuel_type='ev', spec_source='https://www.toyota.com.tw/showroom/bZ4X/fullsepc.aspx', category='ev'),
    dict(id='toyota-urban-cruiser', brand='Toyota', model='URBAN CRUISER', trim='Urban Cruiser', price_twd=1270000, efficiency_km_l=None, source_url='https://www.toyota.com.tw/showroom/URBAN_CRUISER/fullsepc.aspx', source_period='2026-11', checked_on='2026-11-04', displacement_cc=0, fuel_type='ev', spec_source='https://www.toyota.com.tw/showroom/URBAN_CRUISER/fullsepc.aspx', category='ev'),
    dict(id='kia-ev6-light', brand='Kia', model='EV6', trim='Light 標準版', price_twd=1669000, efficiency_km_l=None, source_url='https://www.kia.com/tw/showroom/ev6/features.html', source_period='2026-11', checked_on='2026-11-04', displacement_cc=0, fuel_type='ev', spec_source='https://www.kia.com/tw/showroom/ev6/specification.html', category='ev'),
    dict(id='volvo-ex30-core', brand='Volvo', model='EX30', trim='Core Single Motor Extended Range', price_twd=1399000, efficiency_km_l=None, source_url='https://www.volvocars.com/tw/build/ex30-electric/', source_period='2026-11', checked_on='2026-11-04', displacement_cc=0, fuel_type='ev', spec_source='https://www.volvocars.com/tw/cars/ex30-electric/specifications/', category='ev'),
    dict(id='lexus-ux300h-luxury', brand='Lexus', model='UX', trim='300h 豪華版', price_twd=1499000, efficiency_km_l=24.0, source_url='https://www.lexus.com.tw/showroom/UX/', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1987, fuel_type='hybrid', spec_source='https://www.lexus.com.tw/xml/carspec_xml.ashx?c1=9137&typ=1', category='luxury'),
    dict(id='lexus-nx200-elite', brand='Lexus', model='NX', trim='200 菁英版', price_twd=1710000, efficiency_km_l=15.8, source_url='https://www.lexus.com.tw/showroom/NX/', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1987, fuel_type='gasoline', spec_source='https://www.lexus.com.tw/xml/carspec_xml.ashx?c1=9135&typ=1', category='luxury'),
    dict(id='lexus-nx350h-luxury', brand='Lexus', model='NX', trim='350h 豪華版', price_twd=2075000, efficiency_km_l=19.4, source_url='https://www.lexus.com.tw/showroom/NX/', source_period='2026-11', checked_on='2026-11-04', displacement_cc=2487, fuel_type='hybrid', spec_source='https://www.lexus.com.tw/xml/carspec_xml.ashx?c1=9131&typ=1', category='luxury'),
    dict(id='lexus-es300h-luxury', brand='Lexus', model='ES', trim='300h 豪華版', price_twd=1770000, efficiency_km_l=25.8, source_url='https://www.lexus.com.tw/showroom/ES/', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1987, fuel_type='hybrid', spec_source='https://www.lexus.com.tw/xml/carspec_xml.ashx?c1=9112&typ=1', category='luxury'),
    dict(id='lexus-es500e-premium', brand='Lexus', model='ES', trim='500e 頂級版', price_twd=2050000, efficiency_km_l=None, source_url='https://www.lexus.com.tw/showroom/ES/', source_period='2026-11', checked_on='2026-11-04', displacement_cc=0, fuel_type='ev', spec_source='https://www.lexus.com.tw/xml/carspec_xml.ashx?c1=9110&typ=1', category='ev'),
    dict(id='lexus-lbx-active', brand='Lexus', model='LBX', trim='Active', price_twd=1279000, efficiency_km_l=26.4, source_url='https://www.lexus.com.tw/showroom/LBX/', source_period='2026-11', checked_on='2026-11-04', displacement_cc=1490, fuel_type='hybrid', spec_source='https://www.lexus.com.tw/xml/carspec_xml.ashx?c1=9153&typ=1', category='luxury'),
    dict(id='lexus-is300h-luxury', brand='Lexus', model='IS', trim='300h 豪華版', price_twd=1890000, efficiency_km_l=18.2, source_url='https://www.lexus.com.tw/showroom/IS/', source_period='2026-11', checked_on='2026-11-04', displacement_cc=2494, fuel_type='hybrid', spec_source='https://www.lexus.com.tw/xml/carspec_xml.ashx?c1=9113&typ=1', category='luxury'),
]


def catalog_list(include_ev=False):
    return [{**item, 'currency': 'TWD'} for item in CATALOG
            if include_ev or item['efficiency_km_l'] is not None]


def get_vehicle(vehicle_id):
    item = next((item for item in CATALOG if item['id'] == vehicle_id), None)
    return {**item, 'currency': 'TWD'} if item else None


class VehiclePresetRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    vehicle_id: str = Field(min_length=1, max_length=80)
    annual_distance_km: float = Field(ge=0, le=200000)
    fuel_price_twd_l: float = Field(ge=0, le=200)


def vehicle_preset(request):
    vehicle = get_vehicle(request.vehicle_id)
    if vehicle is None:
        raise ValueError('找不到這個車款，請重新選擇或使用自訂車款。')
    if vehicle['efficiency_km_l'] is None:
        raise ValueError('電動車沒有官方油耗，請自行填寫每月充電費用。')
    monthly_fuel = (Decimal(str(request.annual_distance_km)) / Decimal(str(vehicle['efficiency_km_l']))
                    * Decimal(str(request.fuel_price_twd_l)) / 12)
    return dict(vehicle=vehicle, purchase_price=vehicle['price_twd'],
                monthly_fuel_or_energy=float(monthly_fuel.quantize(Decimal('.01'))),
                annual_distance_km=request.annual_distance_km, fuel_price_twd_l=request.fuel_price_twd_l,
                formula='年里程 ÷ 官方測試油耗 × 每公升油價 ÷ 12',
                warning='官方油耗為實驗室測試值；車價為資料快照，非成交報價。')
