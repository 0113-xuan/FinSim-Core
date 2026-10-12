from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.scenario_schemas import ScenarioRequest, VehiclePurchaseScenarioInput, SourcedDecimal
from app.services.calendar_period import YearMonth
from app.vehicle_catalog import get_vehicle


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ExistingDebt(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    monthly_payment: float = Field(ge=0, le=20000000)
    remaining_months: int = Field(ge=0, le=1200, strict=True)


class DecisionProfile(StrictModel):
    salary: float = Field(ge=0, le=50000000)
    fixed_expense: float = Field(ge=0, le=20000000)
    variable_expense: float = Field(ge=0, le=20000000)
    balance: float = Field(ge=-500000000, le=5000000000)
    required_monthly_debt: float = Field(ge=0, le=20000000)
    existing_debts: list[ExistingDebt] | None = Field(default=None, max_length=50)
    raise_rate: float | None = Field(default=None, ge=-.5, le=1)
    inflation_rate: float | None = Field(default=None, ge=0, le=1)
    fixed_expense_inflates: bool = False

    @model_validator(mode="after")
    def prevent_duplicate_debt(self):
        if self.existing_debts is not None and self.required_monthly_debt != 0:
            raise ValueError("債務明細與每月還款總額不能同時使用")
        if self.existing_debts and sum(d.monthly_payment for d in self.existing_debts) > 20000000:
            raise ValueError("既有月付總額不得超過 2,000 萬元")
        return self


class DecisionConstraints(StrictModel):
    minimum_emergency_fund_months: float | None = Field(default=None, ge=0, le=120)
    minimum_cash_balance: float | None = Field(default=None, ge=0, le=5000000000)
    minimum_monthly_surplus: float | None = Field(default=None, ge=0, le=50000000)


class VehicleDecisionRequest(StrictModel):
    vehicle_catalog_id: str | None = Field(default=None, max_length=80)
    profile: DecisionProfile
    scenario: ScenarioRequest
    start_period: str = Field(pattern=r"^\d{4}-\d{2}$")
    constraints: DecisionConstraints = Field(default_factory=DecisionConstraints)
    assumption_sources: dict[str, Literal['user', 'system_assumption']] = Field(default_factory=dict)

    @model_validator(mode="after")
    def supported_model(self):
        if self.vehicle_catalog_id is not None and get_vehicle(self.vehicle_catalog_id) is None:
            raise ValueError('不支援的車款，請選擇自訂車款或清單中的車型')
        supported_sources = {'profile.raise_rate', 'profile.inflation_rate',
                             *DecisionConstraints.model_fields}
        if self.assumption_sources.keys() - supported_sources:
            raise ValueError("假設來源包含不支援的欄位")
        start = YearMonth.parse(self.start_period)
        if not isinstance(self.scenario.payload, VehiclePurchaseScenarioInput):
            raise ValueError("本入口僅支援購車決策")
        if self.scenario.horizon_months != 60:
            raise ValueError("本階段固定比較 60 個月")
        if start.months_until(self.scenario.target_period) not in range(1, 59):
            raise ValueError("購車月份須落在第 1 至 58 個月，保留完整三個月失業壓測")
        payload = self.scenario.payload
        if payload.purchase_price is None or not 0 < payload.purchase_price.value <= 20000000:
            raise ValueError("車價必須大於零且不超過 2,000 萬元")
        if payload.annual_interest_rate is not None and payload.annual_interest_rate.value > Decimal("0.98"):
            raise ValueError("利率不得超過 98%，需保留壓力測試的 2 個百分點")
        if payload.payment_method == "financed" and payload.down_payment is None:
            raise ValueError("請提供頭期款，零元也需明確填寫")
        for name in type(payload).model_fields:
            item = getattr(payload, name)
            if isinstance(item, SourcedDecimal):
                if not item.value.is_finite() or item.value < 0:
                    raise ValueError(f"{name} 必須為有限非負數")
                if item.source.value not in ("user_provided", "system_assumption", "derived", "backend_normalized"):
                    raise ValueError("決策輸入不可使用未知來源")
        return self


class VehicleComparisonRequest(StrictModel):
    a: VehicleDecisionRequest
    b: VehicleDecisionRequest

    @model_validator(mode="after")
    def shared_financial_context(self):
        if (self.a.profile != self.b.profile or self.a.start_period != self.b.start_period
                or self.a.constraints != self.b.constraints):
            raise ValueError("A/B 必須使用相同財務資料、基準月份與財務限制")
        return self


class VehicleWhatIfRequest(StrictModel):
    request: VehicleDecisionRequest
    field: Literal['salary', 'monthly_parking', 'purchase_price']
    change: float = Field(ge=-20000000, le=20000000)
