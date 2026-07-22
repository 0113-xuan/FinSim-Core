from __future__ import annotations

from enum import Enum
from typing import Annotated, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


NonNegativeAmount = Annotated[float, Field(ge=0, le=1_000_000_000_000)]
Confidence = Annotated[float, Field(ge=0, le=1)]
Percentage = Annotated[float, Field(ge=0, le=100)]


class StrictExtractionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SupportedExtractionField(str, Enum):
    cash_and_deposits = "cash_and_deposits"
    investments = "investments"
    other_assets = "other_assets"
    monthly_salary = "monthly_salary"
    other_recurring_income = "other_recurring_income"
    fixed_expenses = "fixed_expenses"
    total_variable_expenses = "total_variable_expenses"
    monthly_debt_payments = "monthly_debt_payments"
    emergency_fund = "emergency_fund"
    simulation_months = "simulation_months"
    risk_preference = "risk_preference"


class ExtractionSource(str, Enum):
    user_provided = "user_provided"
    ai_extracted = "ai_extracted"
    ai_estimated = "ai_estimated"
    historical_data = "historical_data"
    system_default = "system_default"
    external_research = "external_research"
    user_modified = "user_modified"


class Currency(str, Enum):
    TWD = "TWD"


class ExpenseCategory(str, Enum):
    food = "food"
    transportation = "transportation"
    shopping = "shopping"
    entertainment = "entertainment"
    medical = "medical"
    education = "education"
    travel = "travel"
    other = "other"


class DebtType(str, Enum):
    none = "none"
    mortgage = "mortgage"
    personal_loan = "personal_loan"
    auto_loan = "auto_loan"
    student_loan = "student_loan"
    credit_card = "credit_card"
    other = "other"


class FuturePlanType(str, Enum):
    vehicle_purchase = "vehicle_purchase"
    home_purchase = "home_purchase"
    travel = "travel"
    wedding = "wedding"
    childbirth = "childbirth"
    education = "education"
    business_startup = "business_startup"
    investment = "investment"
    retirement = "retirement"
    other_large_expense = "other_large_expense"
    marriage = "marriage"
    relocation = "relocation"
    job_change = "job_change"
    other = "other"


class InterestRateFrequency(str, Enum):
    monthly = "monthly"
    annual = "annual"
    unspecified = "unspecified"


class InterestRateType(str, Enum):
    annual_percentage = "annual_percentage"
    stated_percentage = "stated_percentage"


class Frequency(str, Enum):
    one_time = "one_time"
    weekly = "weekly"
    biweekly = "biweekly"
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"


class RiskPreference(str, Enum):
    conservative = "conservative"
    balanced = "balanced"
    growth = "growth"
    aggressive = "aggressive"


class FinancialValueRange(StrictExtractionModel):
    minimum: NonNegativeAmount
    maximum: NonNegativeAmount
    midpoint: NonNegativeAmount
    currency: Currency

    @model_validator(mode="after")
    def validate_order(self) -> "FinancialValueRange":
        if self.currency != Currency.TWD:
            raise ValueError("FinSim-Core monetary values must use TWD")
        if self.minimum > self.maximum:
            raise ValueError("range minimum must not exceed maximum")
        if not self.minimum <= self.midpoint <= self.maximum:
            raise ValueError("range midpoint must be within the range")
        expected = (self.minimum + self.maximum) / 2
        if abs(self.midpoint - expected) > 0.01:
            raise ValueError("range midpoint must equal (minimum + maximum) / 2")
        return self


class ExtractedFinancialField(StrictExtractionModel):
    field: SupportedExtractionField
    value: Union[NonNegativeAmount, RiskPreference]
    value_range: FinancialValueRange | None
    currency: Currency | None
    source: ExtractionSource
    confidence: Confidence
    confirmed: bool
    reason: Annotated[str, Field(min_length=1, max_length=300)]
    original_value: Annotated[str, Field(min_length=1, max_length=200)]
    original_amount: NonNegativeAmount | None
    original_frequency: Frequency | None
    normalized_frequency: Frequency | None
    normalized_from: Annotated[str | None, Field(max_length=240)]

    @model_validator(mode="after")
    def validate_field_value(self) -> "ExtractedFinancialField":
        if self.field == SupportedExtractionField.risk_preference:
            if not isinstance(self.value, RiskPreference):
                raise ValueError("risk_preference requires a risk preference enum")
            if self.currency is not None or self.value_range is not None:
                raise ValueError("risk_preference cannot have currency or a numeric range")
        else:
            if isinstance(self.value, RiskPreference):
                raise ValueError("financial fields require numeric values")
            if self.field == SupportedExtractionField.simulation_months:
                if self.value < 1 or not float(self.value).is_integer():
                    raise ValueError("simulation_months must be a positive whole number")
                if self.currency is not None:
                    raise ValueError("simulation_months cannot have currency")
            elif self.currency is None:
                raise ValueError("financial amounts require a currency")
            elif self.currency != Currency.TWD:
                raise ValueError("FinSim-Core monetary values must use TWD")
        recurring_fields = {
            SupportedExtractionField.monthly_salary,
            SupportedExtractionField.other_recurring_income,
            SupportedExtractionField.fixed_expenses,
            SupportedExtractionField.total_variable_expenses,
            SupportedExtractionField.monthly_debt_payments,
        }
        if self.field in recurring_fields and self.original_frequency == Frequency.one_time:
            raise ValueError("one-time amounts cannot be extracted as recurring financial fields")
        if self.normalized_frequency is not None:
            if self.original_frequency in (None, Frequency.monthly, Frequency.one_time):
                raise ValueError("only recurring non-monthly values may be normalized")
            if self.normalized_frequency != Frequency.monthly:
                raise ValueError("normalized frequency must be monthly")
        if self.original_frequency == Frequency.one_time and self.normalized_frequency is not None:
            raise ValueError("one-time values cannot be normalized")
        if self.value_range and self.currency != self.value_range.currency:
            raise ValueError("field and range currencies must match")
        if self.value_range and not isinstance(self.value, RiskPreference):
            if abs(float(self.value) - self.value_range.midpoint) > 0.01:
                raise ValueError("field value must equal the range midpoint")
        return self


class VariableExpenseAllocationItem(StrictExtractionModel):
    category: ExpenseCategory
    amount: NonNegativeAmount
    percentage: Percentage | None
    currency: Currency
    source: ExtractionSource
    confidence: Confidence
    reason: Annotated[str, Field(min_length=1, max_length=300)]
    original_value: Annotated[str, Field(min_length=1, max_length=200)]

    @model_validator(mode="after")
    def validate_currency(self) -> "VariableExpenseAllocationItem":
        if self.currency != Currency.TWD:
            raise ValueError("FinSim-Core monetary values must use TWD")
        return self


class DebtItem(StrictExtractionModel):
    debt_type: DebtType
    name: Annotated[str | None, Field(max_length=100)]
    remaining_balance: NonNegativeAmount | None
    monthly_payment: NonNegativeAmount | None
    annual_interest_rate: Annotated[float | None, Field(ge=0, le=1)]
    remaining_months: Annotated[int | None, Field(ge=0, le=1200)]
    currency: Currency
    source: ExtractionSource
    confidence: Confidence
    reason: Annotated[str, Field(min_length=1, max_length=300)]
    original_value: Annotated[str, Field(min_length=1, max_length=300)]

    @model_validator(mode="after")
    def validate_no_debt(self) -> "DebtItem":
        if self.currency != Currency.TWD:
            raise ValueError("FinSim-Core monetary values must use TWD")
        if self.debt_type == DebtType.none:
            nonzero = (self.remaining_balance or 0) + (self.monthly_payment or 0)
            if nonzero or (self.remaining_months not in (None, 0)):
                raise ValueError("no-debt item cannot contain debt amounts or terms")
        return self


class FuturePlanFinancing(StrictExtractionModel):
    is_financed: bool
    loan_amount: NonNegativeAmount | None
    loan_term_months: Annotated[int | None, Field(ge=1, le=1200)]
    annual_interest_rate: Annotated[float | None, Field(ge=0, le=100)]
    interest_rate_value: Annotated[float | None, Field(ge=0, le=100)]
    interest_rate_frequency: InterestRateFrequency | None
    interest_rate_type: InterestRateType | None
    original_interest_rate_text: Annotated[str | None, Field(max_length=120)]

    @model_validator(mode="after")
    def validate_financing(self) -> "FuturePlanFinancing":
        details = (
            self.loan_amount,
            self.loan_term_months,
            self.annual_interest_rate,
            self.interest_rate_value,
            self.interest_rate_frequency,
            self.interest_rate_type,
            self.original_interest_rate_text,
        )
        if not self.is_financed and any(value is not None for value in details):
            raise ValueError("non-financed plans cannot contain financing details")
        if self.interest_rate_frequency == InterestRateFrequency.monthly:
            if self.interest_rate_value is None:
                raise ValueError("monthly interest requires interest_rate_value")
            if self.annual_interest_rate is not None:
                raise ValueError("monthly interest must not be converted to annual interest")
        if self.annual_interest_rate is not None:
            if self.interest_rate_frequency != InterestRateFrequency.annual:
                raise ValueError("annual interest requires annual frequency")
            if self.interest_rate_type != InterestRateType.annual_percentage:
                raise ValueError("annual interest requires annual_percentage type")
        return self


class FuturePlanItem(StrictExtractionModel):
    plan_type: FuturePlanType
    title: Annotated[str, Field(min_length=1, max_length=100)]
    description: Annotated[str, Field(min_length=1, max_length=300)]
    original_target_date_text: Annotated[str | None, Field(max_length=120)]
    normalized_target_date: Annotated[
        str | None,
        Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    ]
    estimated_cost: NonNegativeAmount | None
    down_payment: NonNegativeAmount | None
    financing: FuturePlanFinancing | None
    recurring_monthly_amount: NonNegativeAmount | None
    currency: Currency
    source: ExtractionSource
    confirmed: bool
    confidence: Confidence
    reason: Annotated[str, Field(min_length=1, max_length=300)]
    source_text: Annotated[str, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def validate_currency(self) -> "FuturePlanItem":
        if self.currency != Currency.TWD:
            raise ValueError("FinSim-Core monetary values must use TWD")
        return self


class FuturePlanConflict(StrictExtractionModel):
    field: Annotated[
        str,
        Field(
            pattern=(
                r"^future_plans\[\d+\]\."
                r"(estimated_cost|down_payment|normalized_target_date|"
                r"financing\.(loan_amount|loan_term_months|annual_interest_rate|"
                r"interest_rate_value|interest_rate_frequency))$"
            )
        ),
    ]
    existing_value: Union[NonNegativeAmount, str]
    candidate_value: Union[NonNegativeAmount, str]
    reason: Annotated[str, Field(min_length=1, max_length=300)]
    requires_user_confirmation: bool

    @model_validator(mode="after")
    def require_confirmation(self) -> "FuturePlanConflict":
        if not self.requires_user_confirmation:
            raise ValueError("future plan conflicts must require user confirmation")
        return self


class ExtractionAmbiguity(StrictExtractionModel):
    field: SupportedExtractionField | None
    message: Annotated[str, Field(min_length=1, max_length=300)]
    clarification_question: Annotated[str, Field(min_length=1, max_length=300)]


class ExtractionConflict(StrictExtractionModel):
    field: SupportedExtractionField
    existing_value: Union[NonNegativeAmount, RiskPreference]
    candidate_value: Union[NonNegativeAmount, RiskPreference]
    reason: Annotated[str, Field(min_length=1, max_length=300)]


class FinancialExtractionResult(StrictExtractionModel):
    fields: Annotated[list[ExtractedFinancialField], Field(max_length=20)]
    variable_expense_allocation: Annotated[
        list[VariableExpenseAllocationItem], Field(max_length=8)
    ]
    debts: Annotated[list[DebtItem], Field(max_length=20)]
    future_plans: Annotated[list[FuturePlanItem], Field(max_length=20)]
    future_plan_conflicts: Annotated[list[FuturePlanConflict], Field(max_length=20)]
    ambiguities: Annotated[list[ExtractionAmbiguity], Field(max_length=20)]
    conflicts: Annotated[list[ExtractionConflict], Field(max_length=20)]

    @model_validator(mode="after")
    def reject_duplicate_candidates(self) -> "FinancialExtractionResult":
        field_names = [item.field for item in self.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError("duplicate field candidates are not allowed")
        categories = [item.category for item in self.variable_expense_allocation]
        if len(categories) != len(set(categories)):
            raise ValueError("duplicate allocation categories are not allowed")
        return self
