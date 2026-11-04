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
]


def catalog_list():
    return [{**item, 'currency': 'TWD'} for item in CATALOG]


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
    monthly_fuel = (Decimal(str(request.annual_distance_km)) / Decimal(str(vehicle['efficiency_km_l']))
                    * Decimal(str(request.fuel_price_twd_l)) / 12)
    return dict(vehicle=vehicle, purchase_price=vehicle['price_twd'],
                monthly_fuel_or_energy=float(monthly_fuel.quantize(Decimal('.01'))),
                annual_distance_km=request.annual_distance_km, fuel_price_twd_l=request.fuel_price_twd_l,
                formula='年里程 ÷ 官方測試油耗 × 每公升油價 ÷ 12',
                warning='官方油耗為實驗室測試值；車價為資料快照，非成交報價。')
