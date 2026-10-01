from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.scenario_schemas import ScenarioRequest, VehiclePurchaseScenarioInput, SourcedDecimal
from app.services.calendar_period import YearMonth


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class DecisionProfile(StrictModel):
    salary: float = Field(ge=0, le=50000000)
    fixed_expense: float = Field(ge=0, le=20000000)
    variable_expense: float = Field(ge=0, le=20000000)
    balance: float = Field(ge=-500000000, le=5000000000)
    required_monthly_debt: float = Field(ge=0, le=20000000)
    raise_rate: float | None = Field(default=None, ge=-.5, le=1)
    inflation_rate: float | None = Field(default=None, ge=0, le=1)
    fixed_expense_inflates: bool = False


class DecisionConstraints(StrictModel):
    minimum_emergency_fund_months: float | None = Field(default=None, ge=0, le=120)
    minimum_cash_balance: float | None = Field(default=None, ge=0, le=5000000000)
    minimum_monthly_surplus: float | None = Field(default=None, ge=0, le=50000000)


class VehicleDecisionRequest(StrictModel):
    profile: DecisionProfile
    scenario: ScenarioRequest
    start_period: str = Field(pattern=r"^\d{4}-\d{2}$")
    constraints: DecisionConstraints = Field(default_factory=DecisionConstraints)

    @model_validator(mode="after")
    def supported_model(self):
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
