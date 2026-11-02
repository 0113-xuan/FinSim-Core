"""Plain numeric inputs for saved planner vehicle events."""
from typing import Literal
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.calendar_period import YearMonth
from app.vehicle_catalog import get_vehicle
from app.vehicle_fees import INSURANCE_IDS


class PlannerModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class PlannerInsuranceItem(PlannerModel):
    id: str
    amount: float = Field(ge=0, le=20_000_000)

    @field_validator('id')
    @classmethod
    def known_insurance(cls, value):
        if value not in INSURANCE_IDS:
            raise ValueError('找不到這個保險項目')
        return value


class PlannerVehicleDetails(PlannerModel):
    vehicle_catalog_id: str | None = Field(default=None, max_length=80)
    purchase_price: float = Field(gt=0, le=20_000_000)
    payment_method: Literal['cash', 'financed']
    down_payment: float | None = Field(default=None, ge=0, le=20_000_000)
    loan_term_months: int | None = Field(default=None, gt=0, le=600, strict=True)
    annual_interest_rate: float | None = Field(default=None, ge=0, le=1)
    annual_insurance: float | None = Field(default=None, ge=0, le=20_000_000)
    annual_tax: float | None = Field(default=None, ge=0, le=20_000_000)
    annual_maintenance_budget: float | None = Field(default=None, ge=0, le=20_000_000)
    monthly_fuel_or_energy: float | None = Field(default=None, ge=0, le=10_000_000)
    monthly_parking: float | None = Field(default=None, ge=0, le=10_000_000)
    annual_depreciation_rate: float | None = Field(default=None, ge=0, le=1)
    displacement_cc: int | None = Field(default=None, ge=0, le=100_000, strict=True)
    fuel_type: Literal['gasoline','hybrid','diesel','ev'] | None = None
    insurance_items: list[PlannerInsuranceItem] | None = Field(default=None, max_length=7)

    @model_validator(mode='after')
    def validate_purchase(self):
        if self.insurance_items is not None:
            ids = [item.id for item in self.insurance_items]
            if 'compulsory' not in ids:
                raise ValueError('保險項目必須包含強制汽車責任保險')
            if len(ids) != len(set(ids)):
                raise ValueError('保險項目不可重複')
            if sum(id.startswith('body_') for id in ids) > 1:
                raise ValueError('甲式、乙式、丙式車體險最多只能選一種')
            total = sum((Decimal(str(item.amount)) for item in self.insurance_items), Decimal('0'))
            if self.annual_insurance is None or abs(total-Decimal(str(self.annual_insurance))) > Decimal('1'):
                raise ValueError('保險合計必須等於各項保費加總，誤差不可超過1元')
        terms = (self.down_payment, self.loan_term_months, self.annual_interest_rate)
        if self.payment_method == 'cash' and any(value is not None for value in terms):
            raise ValueError('現金購車不可填寫貸款條件')
        if self.payment_method == 'financed':
            if any(value is None for value in terms):
                raise ValueError('貸款購車請填寫頭期款、貸款期數及年利率，零元或零利率也需明確填寫')
            if self.down_payment >= self.purchase_price:
                raise ValueError('貸款購車的頭期款必須小於車價，貸款本金須大於零')
        if self.vehicle_catalog_id is not None and get_vehicle(self.vehicle_catalog_id) is None:
            raise ValueError('找不到這個車款，請選擇清單中的車款或自訂車款')
        return self


class PlannerVehicle(PlannerModel):
    name: str = Field(min_length=1, max_length=80)
    purchase_period: str
    details: PlannerVehicleDetails

    @field_validator('purchase_period')
    @classmethod
    def validate_period(cls, value):
        return validate_period(value)


def validate_period(value):
    try:
        period = YearMonth.parse(value)
        if period.year < 1:
            raise ValueError()
    except ValueError:
        raise ValueError('月份須為有效的 YYYY-MM 格式') from None
    return value


class PlannerVehicleRequest(PlannerModel):
    start_period: str
    months: int = Field(gt=0, le=360, strict=True)
    inflation_rate: float | None = Field(default=None, ge=-.5, le=1)
    vehicles: list[PlannerVehicle] = Field(max_length=30)

    _valid_start = field_validator('start_period')(validate_period)

    @model_validator(mode='after')
    def purchases_in_horizon(self):
        start = YearMonth.parse(self.start_period)
        for vehicle in self.vehicles:
            month = start.months_until(YearMonth.parse(vehicle.purchase_period)) + 1
            if not 1 <= month <= self.months:
                raise ValueError(f'購買月份必須落在第 1 至 {self.months} 個月')
        return self
