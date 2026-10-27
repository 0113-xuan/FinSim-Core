"""Validated P1 handoff. Client workflow metadata never supplies vehicle facts."""
from typing import Literal
from pydantic import ConfigDict, Field, StrictBool, field_validator, model_validator
from app.decision_schemas import StrictModel, DecisionProfile
from app.car_needs_ai_schemas import AIExtractionMetadata

Body = Literal['sedan', 'hatchback', 'suv', 'mpv']
Power = Literal['ice', 'hev', 'bev']
Purpose = Literal['commute', 'family', 'work', 'leisure', 'client_transport', 'elderly_transport']
Priority = Literal['space', 'comfort', 'energy_cost', 'maintenance_cost', 'safety']
Charging = Literal['yes', 'no', 'unknown']


class RecommendationModel(StrictModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, strict=True)


class Background(RecommendationModel):
    occupation: Literal['student', 'employee', 'sales', 'self_employed', 'other'] | None = None


class NeedsConstraints(RecommendationModel):
    budget_max: float = Field(gt=0, le=20000000)
    budget_basis: Literal['vehicle_price']
    min_seats: int = Field(strict=True, ge=1, le=9)
    avoid_body_types: list[Body] = Field(max_length=4)


class Usage(RecommendationModel):
    purposes: list[Purpose] = Field(min_length=1, max_length=6)
    monthly_distance_km: float | None = Field(default=None, ge=0, le=16666.66)
    usual_passengers: int = Field(strict=True, ge=1, le=9)
    ownership_years: Literal[1, 3, 5]
    parking_type: Literal['own', 'rented', 'street', 'none'] | None = None
    monthly_parking: float | None = Field(default=None, ge=0, le=20000000)
    home_charging: Charging | None = None
    public_charging: Charging | None = None


class Preferences(RecommendationModel):
    body_types: list[Body] = Field(max_length=4)
    priorities: list[Priority] = Field(max_length=5)
    powertrains: list[Power] = Field(max_length=3)


class Payment(RecommendationModel):
    payment_method: Literal['cash', 'financed'] | None
    down_payment: float | None = Field(default=None, ge=0, le=20000000)
    annual_interest_rate: float | None = Field(default=None, ge=0, le=.98)
    loan_term_months: int | None = Field(default=None, strict=True, ge=1, le=600)

    @model_validator(mode='after')
    def financing(self):
        terms = [self.down_payment, self.annual_interest_rate, self.loan_term_months]
        if self.payment_method == 'financed' and any(v is None for v in terms):
            raise ValueError('貸款須提供頭期款、年利率與期數。')
        if self.payment_method != 'financed' and any(v is not None for v in terms):
            raise ValueError('非貸款付款方式不得夾帶貸款條件。')
        return self


class MockCandidate(RecommendationModel):
    id: str = Field(max_length=80)
    field: Literal['avoid_body_types', 'purposes', 'priorities', 'ownership_years']
    value: str | int
    label: str = Field(max_length=150)
    evidence: str = Field(max_length=1000)
    source: Literal['mock_literal_fixture']


class ExtractionMetadata(RecommendationModel):
    provider: Literal['mock']
    is_real_ai: Literal[False]
    status: Literal['not_requested', 'candidates', 'no_match']
    candidates: list[MockCandidate] = Field(max_length=10)


class Handoff(RecommendationModel):
    status: Literal['ready_for_p2']
    engine_connected: StrictBool


class CarNeedsRequest(RecommendationModel):
    schema_version: Literal['1.0','1.1']
    revision: int = Field(strict=True, ge=0)
    status: Literal['confirmed']
    currency: Literal['TWD']
    background: Background
    constraints: NeedsConstraints
    usage: Usage
    preferences: Preferences
    financial_profile: DecisionProfile | None
    payment: Payment
    free_text: str = Field(max_length=1000)
    extraction: ExtractionMetadata | AIExtractionMetadata
    field_sources: dict[str, Literal['user_provided', 'user_confirmed_mock', 'user_confirmed_ai']] = Field(max_length=40)
    recommendation_handoff: Handoff

    @field_validator('financial_profile', mode='before')
    @classmethod
    def numeric_finances(cls, value):
        if isinstance(value, dict):
            for key in ('salary', 'balance', 'fixed_expense', 'variable_expense', 'required_monthly_debt', 'raise_rate', 'inflation_rate'):
                v = value.get(key)
                if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
                    raise ValueError('財務欄位須使用數值。')
        return value

    @field_validator('constraints', 'usage', 'preferences', 'payment', mode='before')
    @classmethod
    def no_boolean_numbers(cls, value):
        if isinstance(value, dict) and any(isinstance(v, bool) for v in value.values()):
            raise ValueError('數值欄位不可使用布林值。')
        return value

    @model_validator(mode='after')
    def consistent_needs(self):
        if isinstance(self.extraction, AIExtractionMetadata):
            if self.schema_version != '1.1':
                raise ValueError('真實 AI 擷取須使用需求契約 1.1。')
            from app.services.car_needs_extraction import validate_confirmed_ai
            validate_confirmed_ai(self)
        elif self.schema_version != '1.0' or 'user_confirmed_ai' in self.field_sources.values():
            raise ValueError('Mock 與手動需求須使用契約 1.0。')
        if self.constraints.min_seats != self.usage.usual_passengers:
            raise ValueError('乘車人數與最低座位數不一致。')
        if set(self.preferences.body_types) & set(self.constraints.avoid_body_types):
            raise ValueError('車型不可同時偏好與排除。')
        if self.payment.payment_method == 'financed' and self.payment.down_payment >= self.constraints.budget_max:
            raise ValueError('頭期款須小於購車預算。')
        return self
