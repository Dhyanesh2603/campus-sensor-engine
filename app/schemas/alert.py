import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

AlertStatus = Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"]
AlertSeverity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_id: uuid.UUID | None
    sensor_id: str
    trigger_value: float
    threshold: float
    severity: str
    status: str
    triggered_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AlertFilterQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)
    status: AlertStatus | None = None
    severity: AlertSeverity | None = None
    sensor_id: str | None = None
    rule_id: uuid.UUID | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    search: str | None = None
    sort_by: str = Field(default="created_at", pattern="^(created_at|triggered_at|severity|status)$")
    sort_order: Literal["asc", "desc"] = "desc"


class PaginatedAlertsResponse(BaseModel):
    items: list[AlertResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
