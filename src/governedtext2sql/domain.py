"""Closed analytics vocabulary. Models choose concepts, never policy."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Mode(str, Enum):
    baseline = "baseline"
    semantic = "semantic"
    vkg = "vkg"


class Metric(str, Enum):
    eligible_customers = "eligible_customers"
    conversions = "conversions"
    conversion_rate = "conversion_rate"


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: Metric


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=5, max_length=1000)
    mode: Mode = Mode.vkg


class Principal(BaseModel):
    subject: str
    tenant: str
    role: str
