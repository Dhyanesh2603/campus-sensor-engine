from pydantic import BaseModel, Field


class SimulatorStartRequest(BaseModel):
    number_of_sensors: int = Field(default=1000, ge=1, le=10000)
    duration_seconds: int = Field(default=60, ge=1, le=3600)
    batch_size: int = Field(default=500, ge=1, le=5000)
    frequency_per_second: int = Field(default=100, ge=1, le=1000)


class SimulatorStatusResponse(BaseModel):
    is_running: bool
    sensors_configured: int
    duration_seconds: int
    elapsed_seconds: float
    readings_generated: int
    readings_ingested: int
    batches_sent: int
    current_rate_per_sec: float
