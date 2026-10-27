"""Versioned, non-financial AI candidates; no vehicle facts or cost fields."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ALLOWED = {
    'body_types': ('sedan', 'hatchback', 'suv', 'mpv'),
    'avoid_body_types': ('sedan', 'hatchback', 'suv', 'mpv'),
    'priorities': ('space', 'comfort', 'energy_cost', 'maintenance_cost', 'safety'),
    'purposes': ('commute', 'family', 'work', 'leisure', 'client_transport', 'elderly_transport'),
    'powertrains': ('ice', 'hev', 'bev'),
    'ownership_years': (1, 3, 5),
}


class AIModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class NeedsContext(AIModel):
    body_types: list[Literal['sedan','hatchback','suv','mpv']] = Field(max_length=4)
    avoid_body_types: list[Literal['sedan','hatchback','suv','mpv']] = Field(max_length=4)
    priorities: list[Literal['space','comfort','energy_cost','maintenance_cost','safety']] = Field(max_length=5)
    purposes: list[Literal['commute','family','work','leisure','client_transport','elderly_transport']] = Field(max_length=6)
    powertrains: list[Literal['ice','hev','bev']] = Field(max_length=3)
    ownership_years: Literal[1,3,5] | None

    @field_validator('ownership_years', mode='before')
    @classmethod
    def strict_duration(cls, value):
        if value is not None and type(value) is not int:
            raise ValueError('持有年限必須為整數。')
        return value


class NeedsExtractionRequest(AIModel):
    schema_version: Literal['2.0']
    text: str = Field(min_length=1, max_length=1000)
    revision: int = Field(strict=True, ge=0)
    related_answers: NeedsContext


class ExtractedNeed(AIModel):
    field: Literal['body_types','avoid_body_types','priorities','purposes','powertrains','ownership_years']
    operation: Literal['add','remove','set']
    value: Literal['sedan','hatchback','suv','mpv','space','comfort','energy_cost','maintenance_cost','safety','commute','family','work','leisure','client_transport','elderly_transport','ice','hev','bev',1,3,5]
    evidence: str = Field(min_length=1, max_length=200)

    @field_validator('value', mode='before')
    @classmethod
    def strict_value(cls, value):
        if type(value) not in (str, int):
            raise ValueError('候選值必須為支援的文字或整數。')
        return value

    @model_validator(mode='after')
    def supported_operation(self):
        if type(self.value) is bool or self.value not in ALLOWED[self.field]:
            raise ValueError('候選值不符合欄位白名單。')
        if (self.field == 'ownership_years') != (self.operation == 'set'):
            raise ValueError('只有持有年限使用 set，其他欄位僅能 add/remove。')
        return self


class UnclearNeed(AIModel):
    evidence: str = Field(min_length=1, max_length=200)
    reason: Literal['uncertain','unsupported','injection','missing_information']


class ParsedCarNeeds(AIModel):
    candidates: list[ExtractedNeed] = Field(max_length=10)
    unclear: list[UnclearNeed] = Field(max_length=10)


class ReviewCandidate(ExtractedNeed):
    id: str = Field(min_length=1, max_length=20)
    label: str = Field(min_length=1, max_length=150)
    conflict: str | None
    source: Literal['ai_structured']


class AIExtractionMetadata(AIModel):
    schema_version: Literal['2.0']
    provider: Literal['gemini','openai']
    is_real_ai: Literal[True]
    status: Literal['candidates','no_match']
    revision: int = Field(strict=True, ge=0)
    candidates: list[ReviewCandidate] = Field(max_length=10)
    unclear: list[UnclearNeed] = Field(max_length=10)
    receipt: str = Field(min_length=40, max_length=20000)
    expires_at: int = Field(strict=True, ge=0)
    accepted_ids: list[str] = Field(max_length=10)
    rejected_ids: list[str] = Field(max_length=10)
