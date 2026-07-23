from __future__ import annotations

from enum import Enum
from decimal import Decimal
from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_serializer, field_validator, model_validator


MAX_MONTHS = 360
MAX_MONTE_CARLO_ITERATIONS = 5000
MAX_AI_EVENTS = 12


class ExpenseCategoryName(str, Enum):
    food = "food"
    transportation = "transportation"
    entertainment = "entertainment"
    shopping = "shopping"
    medical = "medical"
    education = "education"
    social = "social"
    travel = "travel"
    family_support = "family_support"
    other = "other"


class ExpenseMode(str, Enum):
    quick = "quick"
    advanced = "advanced"


class EventSource(str, Enum):
    manual = "manual"
    ai = "ai"
    system = "system"
    system_assumption = "system_assumption"


class DistributionType(str, Enum):
    uniform = "uniform"
    normal = "normal"


class ExpenseCategoryInput(BaseModel):
    category: ExpenseCategoryName
    baseline: float = Field(..., ge=0, le=5_000_000)
    monthly_volatility: float = Field(default=0.0, ge=0, le=2)
    annual_inflation_rate: float = Field(default=0.02, ge=-0.5, le=1)
    income_elasticity: float = Field(default=0.0, ge=-2, le=2)
    seasonal_factors: List[float] = Field(default_factory=lambda: [1.0] * 12)
    minimum: Optional[float] = Field(default=None, ge=0)
    maximum: Optional[float] = Field(default=None, ge=0)
    enabled: bool = True

    @field_validator("seasonal_factors")
    @classmethod
    def validate_seasonality(cls, value: List[float]) -> List[float]:
        if len(value) != 12:
            raise ValueError("seasonal_factors must contain exactly 12 values")
        if any(item < 0 or item > 5 for item in value):
            raise ValueError("seasonal_factors must be between 0 and 5")
        return value

    @model_validator(mode="after")
    def validate_bounds(self) -> "ExpenseCategoryInput":
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum cannot exceed maximum")
        return self


class VariableExpenseModel(BaseModel):
    mode: ExpenseMode = ExpenseMode.quick
    total_variable_expense: float = Field(default=0, ge=0, le=20_000_000)
    categories: List[ExpenseCategoryInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_model(self) -> "VariableExpenseModel":
        if self.mode == ExpenseMode.advanced and not self.categories:
            raise ValueError("advanced mode requires at least one category")
        return self


class LoanInput(BaseModel):
    principal: float = Field(..., ge=0, le=500_000_000)
    apr: float = Field(..., ge=0, le=1)
    months: int = Field(..., gt=0, le=600)
    start_month: int = Field(..., gt=0, le=MAX_MONTHS)
    note: Optional[str] = Field(default=None, max_length=120)


class EventInput(BaseModel):
    type: Literal["one_time", "range", "salary_change", "life_event"] = "life_event"
    name: str = Field(default="Life event", max_length=80)
    description: Optional[str] = Field(default=None, max_length=500)
    month: Optional[int] = Field(default=None, gt=0, le=MAX_MONTHS)
    start_month: Optional[int] = Field(default=None, gt=0, le=MAX_MONTHS)
    end_month: Optional[int] = Field(default=None, gt=0, le=MAX_MONTHS)
    start_period: Optional[str] = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    end_period: Optional[str] = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount: Optional[float] = Field(default=None, ge=-20_000_000, le=20_000_000)
    new_salary: Optional[float] = Field(default=None, ge=0, le=50_000_000)
    one_time_amount: float = Field(default=0, ge=-50_000_000, le=50_000_000)
    monthly_amount: float = Field(default=0, ge=-10_000_000, le=10_000_000)
    category_monthly_adjustment: float = Field(default=0, ge=-10_000_000, le=10_000_000)
    income_multiplier: float = Field(default=1.0, ge=0, le=5)
    fixed_expense_multiplier: float = Field(default=1.0, ge=0, le=5)
    variable_expense_multiplier: float = Field(default=1.0, ge=0, le=5)
    target_expense_category: Optional[ExpenseCategoryName] = None
    expense_role: Literal["additional", "replacement", "offset"] = "additional"
    display_source: str = Field(default="使用者輸入", max_length=40)
    reason: str = Field(default="", max_length=200)
    assumption_key: Optional[str] = Field(default=None, max_length=120)
    probability: float = Field(default=1.0, ge=0, le=1)
    source: EventSource = EventSource.manual
    note: Optional[str] = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def normalize_legacy_events(self) -> "EventInput":
        if self.type == "one_time" and self.month is None:
            raise ValueError("one_time events require month")
        if self.type in ("range", "salary_change", "life_event") and self.start_month is None:
            raise ValueError(f"{self.type} events require start_month")
        if self.end_month is not None and self.start_month is not None and self.end_month < self.start_month:
            raise ValueError("end_month cannot be earlier than start_month")
        return self


class RandomShockInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    target_category: Optional[ExpenseCategoryName] = None
    monthly_probability: float = Field(..., ge=0, le=1)
    min_amount: float = Field(..., ge=0, le=50_000_000)
    max_amount: float = Field(..., ge=0, le=50_000_000)
    duration_months: int = Field(default=1, ge=1, le=24)
    distribution: DistributionType = DistributionType.uniform
    enabled: bool = True

    @model_validator(mode="after")
    def validate_range(self) -> "RandomShockInput":
        if self.min_amount > self.max_amount:
            raise ValueError("min_amount cannot exceed max_amount")
        return self


class ProfileInput(BaseModel):
    salary: float = Field(..., ge=0, le=50_000_000)
    fixed_expense: float = Field(..., ge=0, le=20_000_000)
    variable_expense: float = Field(default=0, ge=0, le=20_000_000)
    balance: float = Field(..., ge=-500_000_000, le=5_000_000_000)
    raise_rate: float = Field(default=0.03, ge=-0.5, le=1)
    inflation_rate: float = Field(default=0.02, ge=-0.5, le=1)
    target_emergency_months: float = Field(default=3, gt=0, le=36)
    variable_expense_model: Optional[VariableExpenseModel] = None

    @model_validator(mode="after")
    def ensure_legacy_variable_expense(self) -> "ProfileInput":
        if self.variable_expense_model is None:
            self.variable_expense_model = VariableExpenseModel(
                mode=ExpenseMode.quick,
                total_variable_expense=self.variable_expense,
            )
        elif self.variable_expense_model.mode == ExpenseMode.quick:
            self.variable_expense = self.variable_expense_model.total_variable_expense
        return self


class SimulationRequest(BaseModel):
    profile: ProfileInput
    months: int = Field(default=60, gt=0, le=MAX_MONTHS)
    events: List[EventInput] = Field(default_factory=list)
    loans: List[LoanInput] = Field(default_factory=list)
    random_shocks: List[RandomShockInput] = Field(default_factory=list)
    seed: Optional[int] = Field(default=None, ge=0)
    include_details: bool = False
    user_id: Optional[str] = None
    scenario_context: List["ScenarioContext"] = Field(default_factory=list, max_length=MAX_AI_EVENTS)


class MonteCarloRequest(SimulationRequest):
    simulations: int = Field(default=300, gt=0, le=MAX_MONTE_CARLO_ITERATIONS)
    sample_paths: int = Field(default=8, ge=0, le=25)


class OptionInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    events: List[EventInput] = Field(default_factory=list)
    loans: List[LoanInput] = Field(default_factory=list)
    random_shocks: List[RandomShockInput] = Field(default_factory=list)
    profile_overrides: Dict[str, Any] = Field(default_factory=dict)


class CompareRequest(BaseModel):
    profile: ProfileInput
    options: List[OptionInput] = Field(..., min_length=1, max_length=12)
    months: int = Field(default=60, gt=0, le=MAX_MONTHS)
    mc_runs: int = Field(default=300, gt=0, le=MAX_MONTE_CARLO_ITERATIONS)
    seed: Optional[int] = Field(default=None, ge=0)


class OptimizationConstraints(BaseModel):
    bankruptcy_probability_below: Optional[float] = Field(default=None, ge=0, le=1)
    minimum_emergency_months_above: Optional[float] = Field(default=None, ge=0, le=36)
    maximum_fsi_below: Optional[float] = Field(default=None, ge=0, le=5)
    balance_must_not_be_negative: bool = False
    debt_to_income_below: Optional[float] = Field(default=None, ge=0, le=5)


class OptimizeRequest(BaseModel):
    profile: ProfileInput
    months: int = Field(default=60, gt=0, le=MAX_MONTHS)
    constraints: OptimizationConstraints = Field(default_factory=OptimizationConstraints)
    max_candidates: int = Field(default=24, gt=0, le=60)
    seed: Optional[int] = Field(default=None, ge=0)


class ScenarioParseRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=2000)
    months: int = Field(default=60, gt=0, le=MAX_MONTHS)
    reference_date: Optional[date] = None
    timezone: str = Field(default="Asia/Taipei", min_length=1, max_length=80)
    profile_draft_id: Optional[str] = Field(default=None, min_length=8, max_length=80)


class ScenarioAssumption(BaseModel):
    key: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., max_length=160)
    suggested_value: Optional[str] = Field(default=None, max_length=160)
    source: str = Field(default="來源未標示", max_length=40)
    editable: bool = True


class ScenarioSourceItem(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., max_length=160)
    source: str = Field(default="來源未標示", max_length=40)
    estimated: bool = True


class ScenarioContext(BaseModel):
    id: str = Field(default="scenario", min_length=1, max_length=80)
    title: str = Field(default="AI 建立的財務情境", max_length=120)
    scenario_type: str = Field(default="生活事件", max_length=80)
    start_month: int = Field(default=1, gt=0, le=MAX_MONTHS)
    start_period: Optional[str] = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    end_period: Optional[str] = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    original_target_date_text: Optional[str] = Field(default=None, max_length=80)
    duration_months: int = Field(default=1, gt=0, le=MAX_MONTHS)
    one_time_cost: float = Field(default=0, ge=0, le=50_000_000)
    recurring_monthly_cost: float = Field(default=0, ge=0, le=10_000_000)
    low_estimate: float = Field(default=0, ge=0, le=100_000_000)
    expected_estimate: float = Field(default=0, ge=0, le=100_000_000)
    high_estimate: float = Field(default=0, ge=0, le=100_000_000)
    confidence: float = Field(default=0.5, ge=0, le=1)
    status: Literal[
        "AI 建議",
        "等待確認",
        "使用者已確認",
        "使用者已修改",
        "使用系統預設",
    ] = "等待確認"
    assumptions: List[ScenarioAssumption] = Field(default_factory=list, max_length=30)
    sources: List[ScenarioSourceItem] = Field(default_factory=list, max_length=30)


class ExpenseAdjustment(BaseModel):
    category: ExpenseCategoryName
    start_month: int = Field(..., gt=0, le=MAX_MONTHS)
    end_month: Optional[int] = Field(default=None, gt=0, le=MAX_MONTHS)
    start_period: Optional[str] = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    end_period: Optional[str] = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    multiplier: float = Field(default=1.0, ge=0, le=3)
    monthly_amount: float = Field(default=0, ge=-1_000_000, le=1_000_000)
    reason: str = Field(default="", max_length=200)
    expense_role: Literal["additional", "replacement", "offset"] = "additional"
    source: str = Field(default="來源未標示", max_length=40)
    assumption_key: Optional[str] = Field(default=None, max_length=120)


class ScenarioKnownValue(BaseModel):
    key: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., min_length=1, max_length=160)
    source: str = Field(default="來源未標示", max_length=40)


class ScenarioCandidate(BaseModel):
    id: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=100)
    monthly_amount: float = Field(..., ge=0, le=10_000_000)
    source: Literal["user_provided", "system_assumption"]
    display_source: Literal["使用者提供", "系統模擬假設"]
    comparison_months: int = Field(default=60, gt=0, le=MAX_MONTHS)
    derived_total: float = Field(..., ge=0, le=500_000_000)
    derived_source: Literal["derived"] = "derived"
    derived_display_source: Literal["系統計算"] = "系統計算"


class ScenarioClarification(BaseModel):
    intent: Literal[
        "vehicle_purchase",
        "relocation",
        "insurance_purchase",
        "savings_change",
        "work_break",
        "job_change",
    ]
    summary: str = Field(..., min_length=1, max_length=300)
    known_values: List[ScenarioKnownValue] = Field(default_factory=list, max_length=20)
    candidates: List[ScenarioCandidate] = Field(default_factory=list, max_length=12)
    missing_fields: List[str] = Field(default_factory=list, max_length=20)
    questions: List[str] = Field(default_factory=list, min_length=1, max_length=8)
    system_assumption_offer: Optional[str] = Field(default=None, max_length=300)


class ParsedScenario(BaseModel):
    summary: str = Field(..., max_length=300)
    expense_adjustments: List[ExpenseAdjustment] = Field(default_factory=list, max_length=MAX_AI_EVENTS)
    events: List[EventInput] = Field(default_factory=list, max_length=MAX_AI_EVENTS)
    confidence: float = Field(..., ge=0, le=1)
    warnings: List[str] = Field(default_factory=list)
    display: Optional[ScenarioContext] = None
    provider_used: bool = False
    fallback_used: bool = False
    fallback_type: Optional[str] = Field(default=None, max_length=80)
    fallback_reason: Optional[str] = Field(default=None, max_length=80)
    clarification: Optional[ScenarioClarification] = None
    typed_scenario_request: Optional[Dict[str, Any]] = None
    typed_missing_fields: List[str] = Field(default_factory=list, max_length=30)


class CategorizeExpensesRequest(BaseModel):
    total_variable_expense: float = Field(..., ge=0, le=20_000_000)
    descriptions: List[str] = Field(default_factory=list, max_length=50)


class CategorySuggestion(BaseModel):
    category: ExpenseCategoryName
    amount: float = Field(..., ge=0)
    confidence: float = Field(..., ge=0, le=1)
    reason: str = Field(default="", max_length=200)


class CategorizeExpensesResponse(BaseModel):
    categories: List[CategorySuggestion]
    total: float
    warnings: List[str] = Field(default_factory=list)


class GenerateReportRequest(BaseModel):
    simulation_result: Dict[str, Any]
    monte_carlo_result: Optional[Dict[str, Any]] = None
    comparison_result: Optional[Dict[str, Any]] = None


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=40)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=40)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class FinancialProfileCreate(BaseModel):
    current_savings: int = Field(..., ge=-500_000_000)
    monthly_income: int = Field(..., ge=0)
    has_loan: bool
    loan_amount: int = Field(default=0, ge=0)


class FinanceEvent(BaseModel):
    event_type: str = Field(..., max_length=80)
    amount: float


class ProfileValueSource(str, Enum):
    user_provided = "user_provided"
    ai_extracted = "ai_extracted"
    ai_estimated = "ai_estimated"
    historical_data = "historical_data"
    system_default = "system_default"
    external_research = "external_research"
    user_modified = "user_modified"
    backend_normalized = "backend_normalized"


class DraftFieldValue(BaseModel):
    value: Any = None
    source: ProfileValueSource
    confidence: float = Field(..., ge=0, le=1)
    confirmed: bool = False
    reason: str = Field(default="", max_length=300)
    original_message_ref: Optional[str] = Field(default=None, max_length=80)
    original_value: Any = None
    normalized_from: Optional[str] = Field(default=None, max_length=120)
    original_amount: Optional[float] = Field(default=None, ge=0)
    original_frequency: Optional[str] = Field(default=None, max_length=40)
    normalization_source: Optional[str] = Field(default=None, max_length=40)

    @field_serializer("value", when_used="json")
    def serialize_decimal_value(self, value: Any) -> Any:
        return float(value) if isinstance(value, Decimal) else value


class VariableExpenseAllocationDraft(BaseModel):
    category: Literal[
        "food",
        "transportation",
        "shopping",
        "entertainment",
        "medical",
        "education",
        "travel",
        "other",
    ]
    amount: float = Field(..., ge=0, le=20_000_000)
    percentage: float = Field(..., ge=0, le=100)
    source: ProfileValueSource
    confidence: float = Field(..., ge=0, le=1)
    confirmed: bool = False
    reason: str = Field(default="", max_length=300)


class DebtDraft(BaseModel):
    name: str = Field(default="債務", max_length=80)
    principal: DraftFieldValue
    monthly_payment: DraftFieldValue
    annual_interest_rate: Optional[DraftFieldValue] = None
    remaining_months: Optional[DraftFieldValue] = None


class FinancialProfileDraft(BaseModel):
    id: str = Field(..., min_length=8, max_length=80)
    version: int = Field(default=1, ge=1)
    status: Literal["collecting", "review", "confirmed", "cancelled"] = "collecting"
    cash_and_deposits: DraftFieldValue
    investments: DraftFieldValue
    other_assets: DraftFieldValue
    monthly_salary: DraftFieldValue
    other_recurring_income: DraftFieldValue
    fixed_expenses: DraftFieldValue
    total_variable_expenses: DraftFieldValue
    monthly_debt_payments: DraftFieldValue
    emergency_fund: DraftFieldValue
    simulation_months: DraftFieldValue
    risk_preference: DraftFieldValue
    variable_expense_allocation: List[VariableExpenseAllocationDraft] = Field(default_factory=list, max_length=8)
    debts: List[DebtDraft] = Field(default_factory=list, max_length=20)
    future_plans: List[DraftFieldValue] = Field(default_factory=list, max_length=20)
    validation_errors: List[str] = Field(default_factory=list, max_length=30)
    conflicts: List[str] = Field(default_factory=list, max_length=20)
    missing_required: List[str] = Field(default_factory=list, max_length=20)
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list, max_length=200)
    created_at: str
    updated_at: str
    confirmed_at: Optional[str] = None


class FinancialOnboardingMessageRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    draft_id: Optional[str] = Field(default=None, min_length=8, max_length=80)


class FinancialOnboardingMessageResponse(BaseModel):
    draft: FinancialProfileDraft
    assistant_message: str = Field(..., max_length=800)
    follow_up_questions: List[str] = Field(default_factory=list, max_length=5)
    ready_for_review: bool
    provider_available: bool
    current_step: int = Field(default=1, ge=1)
    total_steps: int = Field(default=5, ge=1)
    stage_label: str = Field(default="財務概況", max_length=40)


class FinancialProfileDraftUpdate(BaseModel):
    draft: FinancialProfileDraft


class FinancialProfileDraftConfirm(BaseModel):
    draft: FinancialProfileDraft
    explicit_confirmation: bool = False
