from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


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


class ScenarioAssumption(BaseModel):
    key: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., max_length=160)
    suggested_value: Optional[str] = Field(default=None, max_length=160)
    source: str = Field(default="AI 推估", max_length=40)
    editable: bool = True


class ScenarioSourceItem(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., max_length=160)
    source: str = Field(default="AI 推估", max_length=40)
    estimated: bool = True


class ScenarioContext(BaseModel):
    id: str = Field(default="scenario", min_length=1, max_length=80)
    title: str = Field(default="AI 建立的財務情境", max_length=120)
    scenario_type: str = Field(default="生活事件", max_length=80)
    start_month: int = Field(default=1, gt=0, le=MAX_MONTHS)
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
    multiplier: float = Field(default=1.0, ge=0, le=3)
    monthly_amount: float = Field(default=0, ge=-1_000_000, le=1_000_000)
    reason: str = Field(default="", max_length=200)
    expense_role: Literal["additional", "replacement", "offset"] = "additional"
    source: str = Field(default="AI 推估", max_length=40)


class ParsedScenario(BaseModel):
    summary: str = Field(..., max_length=300)
    expense_adjustments: List[ExpenseAdjustment] = Field(default_factory=list, max_length=MAX_AI_EVENTS)
    events: List[EventInput] = Field(default_factory=list, max_length=MAX_AI_EVENTS)
    confidence: float = Field(..., ge=0, le=1)
    warnings: List[str] = Field(default_factory=list)
    display: Optional[ScenarioContext] = None


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
