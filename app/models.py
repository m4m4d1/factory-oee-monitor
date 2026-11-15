"""Data model for production records and downtime events."""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from .config import DOWNTIME_REASONS, LINE_IDS


def known_line(v: str) -> str:
    if v not in LINE_IDS:
        raise ValueError(f"unknown line '{v}'")
    return v


class ProductionIn(BaseModel):
    """Output of one line over one period (normally one hour) from a PLC, MES or the line leader."""

    line_id: str
    timestamp: datetime | None = Field(None, description="Start of the period; defaults to now (UTC)")
    planned_minutes: float = Field(..., ge=0, le=60, description="Planned production time in the period")
    run_minutes: float = Field(..., ge=0, le=60, description="Time the line actually ran")
    total_count: int = Field(..., ge=0, le=1_000_000, description="Units produced, good and rejected")
    good_count: int = Field(..., ge=0, le=1_000_000, description="Units right first time")

    @field_validator("line_id")
    @classmethod
    def line_exists(cls, v: str) -> str:
        return known_line(v)

    @model_validator(mode="after")
    def consistent(self):
        if self.run_minutes > self.planned_minutes:
            raise ValueError("run_minutes cannot exceed planned_minutes")
        if self.good_count > self.total_count:
            raise ValueError("good_count cannot exceed total_count")
        return self


class DowntimeIn(BaseModel):
    """One stop of a line, reported when it ends."""

    line_id: str
    start: datetime | None = Field(None, description="When the line stopped; defaults to now (UTC)")
    minutes: float = Field(..., gt=0, le=24 * 60, description="How long the line was stopped")
    reason: str = Field(..., description="One of: " + ", ".join(DOWNTIME_REASONS))

    @field_validator("line_id")
    @classmethod
    def line_exists(cls, v: str) -> str:
        return known_line(v)

    @field_validator("reason")
    @classmethod
    def known_reason(cls, v: str) -> str:
        if v not in DOWNTIME_REASONS:
            raise ValueError(f"unknown reason '{v}'")
        return v


class Production(ProductionIn):
    timestamp: datetime


class Downtime(DowntimeIn):
    start: datetime
