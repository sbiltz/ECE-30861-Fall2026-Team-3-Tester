"""Response schemas for the course tester interface."""
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class SessionRef(BaseModel):
    session_id: str = Field(min_length=1)


class TestError(BaseModel):
    message: str = Field(min_length=1)
    source: Literal['tester','system','communication','unknown']


class TestResult(BaseModel):
    test_id: str = Field(min_length=1)
    outcome: Literal['pass','fail','error','skip']
    message: str = Field(min_length=1)
    source: Literal['tester','system','communication','unknown'] | None = None

    @model_validator(mode='after')
    def error_source(self):
        if self.outcome == 'error' and self.source is None:
            raise ValueError('Error results require a source')
        return self


class Measure(BaseModel):
    covered: int | None = Field(ge=0)
    total: int | None = Field(ge=0)
    basis: str = Field(min_length=1)

    @model_validator(mode='after')
    def valid_counts(self):
        if (self.covered is None) != (self.total is None):
            raise ValueError('Counts must both be null when unavailable')
        if self.covered is not None and self.covered > self.total:
            raise ValueError('Covered cannot exceed total')
        return self


class Coverage(BaseModel):
    code: Measure
    component: Measure
    system: Measure


class SuiteReport(BaseModel):
    session_id: str = Field(min_length=1)
    target_url: str = Field(min_length=1)
    results: list[TestResult]
    coverage: Coverage
