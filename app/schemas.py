from typing import List, Optional, Literal
from pydantic import BaseModel, Field, EmailStr


class FinanceEvent(BaseModel):
    user_id: str
    event_type: str
    amount: float


class LoanInput(BaseModel):
    principal: float = Field(..., ge=0)
    apr: float = Field(..., ge=0)
    months: int = Field(..., gt=0)
    start_month: int = Field(..., gt=0)


class EventInput(BaseModel):
    type: Literal["one_time", "range", "salary_change"]
    month: Optional[int] = Field(default=None, gt=0)
    start_month: Optional[int] = Field(default=None, gt=0)
    end_month: Optional[int] = Field(default=None, gt=0)
    amount: Optional[float] = None
    new_salary: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = None


class ProfileInput(BaseModel):
    salary: float = Field(..., ge=0)
    fixed_expense: float = Field(..., ge=0)
    variable_expense: float = Field(..., ge=0)
    balance: float
    raise_rate: float = Field(default=0.03, ge=0)
    inflation_rate: float = Field(default=0.02, ge=0)
    target_emergency_months: float = Field(default=3, gt=0)


class SimulationRequest(BaseModel):
    profile: ProfileInput
    months: int = Field(default=60, gt=0)
    events: List[EventInput] = []
    loans: List[LoanInput] = []
    user_id: Optional[str] = None


class MonteCarloRequest(BaseModel):
    profile: ProfileInput
    months: int = Field(default=60, gt=0)
    events: List[EventInput] = []
    loans: List[LoanInput] = []
    simulations: int = Field(default=300, gt=0)


class OptionInput(BaseModel):
    name: str
    events: List[EventInput] = []
    loans: List[LoanInput] = []


class CompareRequest(BaseModel):
    profile: ProfileInput
    options: List[OptionInput]
    months: int = Field(default=60, gt=0)
    mc_runs: int = Field(default=300, gt=0)


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class FinancialProfileCreate(BaseModel):
    user_id: str
    current_savings: int
    monthly_income: int
    has_loan: bool
    loan_amount: int = 0
