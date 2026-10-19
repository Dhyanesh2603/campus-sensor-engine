import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

WINDOW_MAP: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "10m": 600,
    "30m": 1800,
    "1h": 3600,
    "1 minute": 60,
    "5 minutes": 300,
    "10 minutes": 600,
    "30 minutes": 1800,
    "1 hour": 3600,
}

RuleType = Literal["threshold", "window"]
OperatorType = Literal[">", ">=", "<", "<=", "==", "!="]
AggregationType = Literal["AVG", "MIN", "MAX", "COUNT"]
SeverityType = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class RuleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    sensor_type: str = Field(..., min_length=1, max_length=50)
    rule_type: RuleType
    operator: OperatorType
    threshold: float
    aggregation: AggregationType | None = None
    window: str | None = None
    cooldown_seconds: int = Field(default=300, ge=0, le=86400)
    enabled: bool = True
    severity: SeverityType = "MEDIUM"

    @model_validator(mode="after")
    def validate_window_rule_requirements(self) -> "RuleCreateRequest":
        if self.rule_type == "window":
            if not self.aggregation:
                raise ValueError("Aggregation (AVG, MIN, MAX, COUNT) is required for window rules")
            if not self.window:
                raise ValueError("Window (e.g. 1m, 5m, 10m, 30m, 1h) is required for window rules")
            clean_window = self.window.strip().lower()
            if clean_window not in WINDOW_MAP:
                raise ValueError(
                    f"Unsupported window: {self.window}. Must be one of 1m, 5m, 10m, 30m, 1h"
                )
        return self


class RuleUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    sensor_type: str | None = None
    rule_type: RuleType | None = None
    operator: OperatorType | None = None
    threshold: float | None = None
    aggregation: AggregationType | None = None
    window: str | None = None
    cooldown_seconds: int | None = Field(default=None, ge=0, le=86400)
    enabled: bool | None = None
    severity: SeverityType | None = None


class RuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    sensor_type: str
    rule_type: str
    operator: str
    threshold: float
    aggregation: str | None
    window: str | None
    window_seconds: int | None
    cooldown_seconds: int
    enabled: bool
    severity: str
    created_at: datetime
    updated_at: datetime
