from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class SensorReadingIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sensor_id: str = Field(..., alias="sensorId", min_length=1, max_length=100)
    sensor_type: str = Field(..., alias="type", min_length=1, max_length=50)
    value: float
    timestamp: datetime


class SensorCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    sensor_type: str = Field(..., min_length=1, max_length=50)
    location: str | None = None
    is_active: bool = True
    metadata_json: dict[str, Any] | None = None


class SensorUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    is_active: bool | None = None
    metadata_json: dict[str, Any] | None = None


class SensorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    sensor_type: str
    location: str | None
    is_active: bool
    metadata_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class SensorReadingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sensor_id: str
    sensor_type: str
    value: float
    timestamp: datetime
    created_at: datetime


class IngestionSummary(BaseModel):
    total_received: int
    ingested_count: int
    failed_count: int
    alerts_triggered: int
    duration_ms: float
