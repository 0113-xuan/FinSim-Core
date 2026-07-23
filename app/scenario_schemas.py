from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from app.schemas import EventInput, LoanInput, ProfileInput
from app.services.calendar_period import YearMonth


class StrictScenarioModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScenarioType(str, Enum):
    vehicle_purchase = "vehicle_purchase"
    housing_change = "housing_change"


class ValueSource(str, Enum):
    user_provided = "user_provided"
    derived = "derived"
    backend_normalized = "backend_normalized"
    system_assumption = "system_assumption"
    unknown = "unknown"


class SourcedDecimal(StrictScenarioModel):
    value: Decimal
    source: ValueSource
    original_text: Optional[str] = Field(default=None, max_length=300)


class ScenarioFact(StrictScenarioModel):
    field: str = Field(min_length=1, max_length=80)
    value: Optional[Decimal] = None
    source: ValueSource
    display_source: str = Field(min_length=1, max_length=40)
    reason: str = Field(default="", max_length=300)


class VehiclePurchaseScenarioInput(StrictScenarioModel):
    scenario_type: Literal[ScenarioType.vehicle_purchase]
    purchase_price: Optional[SourcedDecimal] = None
    vehicle_condition: Optional[Literal["new", "used", "unknown"]] = None
    payment_method: Literal["cash", "financed"]
    down_payment: Optional[SourcedDecimal] = None
    explicit_loan_amount: Optional[SourcedDecimal] = None
    loan_term_months: Optional[int] = Field(default=None, gt=0, le=600)
    annual_interest_rate: Optional[SourcedDecimal] = None
    annual_insurance: Optional[SourcedDecimal] = None
    annual_tax: Optional[SourcedDecimal] = None
    annual_maintenance_budget: Optional[SourcedDecimal] = None
    monthly_fuel_or_energy: Optional[SourcedDecimal] = None
    monthly_parking: Optional[SourcedDecimal] = None


class HousingChangeScenarioInput(StrictScenarioModel):
    scenario_type: Literal[ScenarioType.housing_change]
    current_rent: Optional[SourcedDecimal] = None
    new_rent: Optional[SourcedDecimal] = None
    monthly_rent_change: Optional[SourcedDecimal] = None
    monthly_commute_change: Optional[SourcedDecimal] = None
    deposit: Optional[SourcedDecimal] = None
    moving_cost: Optional[SourcedDecimal] = None
    broker_fee: Optional[SourcedDecimal] = None
    deposit_refundable: Optional[bool] = None


ScenarioPayload = Annotated[
    Union[VehiclePurchaseScenarioInput, HousingChangeScenarioInput],
    Field(discriminator="scenario_type"),
]


class ScenarioRequest(StrictScenarioModel):
    scenario_id: str = Field(min_length=1, max_length=80)
    scenario_type: ScenarioType
    target_period: YearMonth
    horizon_months: int = Field(gt=0, le=360)
    payload: ScenarioPayload
    missing_fields: list[str] = Field(default_factory=list, max_length=30)
    assumptions: list[ScenarioFact] = Field(default_factory=list, max_length=30)
    source_metadata: list[ScenarioFact] = Field(default_factory=list, max_length=50)
    original_text: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("target_period", mode="before")
    @classmethod
    def parse_target_period(cls, value: object) -> YearMonth:
        if isinstance(value, YearMonth):
            return value
        if isinstance(value, str):
            return YearMonth.parse(value)
        raise ValueError("target_period must use YYYY-MM")

    @field_serializer("target_period")
    def serialize_target_period(self, value: YearMonth) -> str:
        return str(value)

    @model_validator(mode="after")
    def validate_payload_type(self) -> "ScenarioRequest":
        if self.payload.scenario_type != self.scenario_type:
            raise ValueError("scenario_type must match payload.scenario_type")
        return self


class ScenarioOption(StrictScenarioModel):
    option_id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    is_baseline: bool = False
    scenario_request: Optional[ScenarioRequest] = None
    assumptions: list[ScenarioFact] = Field(default_factory=list, max_length=30)
    provenance: list[ScenarioFact] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_baseline_semantics(self) -> "ScenarioOption":
        if self.is_baseline:
            if self.option_id != "baseline":
                raise ValueError('baseline option_id must be "baseline"')
            if self.scenario_request is not None:
                raise ValueError("baseline must not contain a scenario_request")
        elif self.scenario_request is None:
            raise ValueError("non-baseline option requires scenario_request")
        return self


class ScenarioBuildResult(StrictScenarioModel):
    scenario_request: ScenarioRequest
    events: list[EventInput] = Field(default_factory=list)
    loans: list[LoanInput] = Field(default_factory=list)
    assumptions: list[ScenarioFact] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    derived_values: list[ScenarioFact] = Field(default_factory=list)


class ScenarioDelta(StrictScenarioModel):
    baseline_option_id: str
    scenario_option_id: str
    final_cash_difference: Decimal
    average_monthly_cash_flow_difference: Decimal
    minimum_cash_balance: Decimal
    minimum_balance_period: YearMonth
    first_deficit_period: Optional[YearMonth]
    total_new_debt: Decimal
    total_interest: Decimal
    one_time_cost_total: Decimal
    recurring_cost_total: Decimal
    assumptions: list[ScenarioFact] = Field(default_factory=list)

    @field_serializer("minimum_balance_period", "first_deficit_period")
    def serialize_period(self, value: Optional[YearMonth]) -> Optional[str]:
        return str(value) if value is not None else None


class ScenarioComparisonRequest(StrictScenarioModel):
    confirmed_profile: ProfileInput
    start_period: YearMonth
    horizon_months: int = Field(default=60, gt=0, le=360)
    options: list[ScenarioOption] = Field(min_length=1, max_length=12)
    seed: Optional[int] = Field(default=0, ge=0)

    @field_validator("start_period", mode="before")
    @classmethod
    def parse_start_period(cls, value: object) -> YearMonth:
        if isinstance(value, YearMonth):
            return value
        if isinstance(value, str):
            return YearMonth.parse(value)
        raise ValueError("start_period must use YYYY-MM")

    @field_serializer("start_period")
    def serialize_start_period(self, value: YearMonth) -> str:
        return str(value)


class ScenarioOptionResult(StrictScenarioModel):
    option: ScenarioOption
    build: Optional[ScenarioBuildResult] = None
    simulation: dict


class ScenarioComparisonResponse(StrictScenarioModel):
    baseline: ScenarioOptionResult
    scenarios: list[ScenarioOptionResult] = Field(default_factory=list)
    deltas: list[ScenarioDelta] = Field(default_factory=list)
    baseline_only: bool = False
