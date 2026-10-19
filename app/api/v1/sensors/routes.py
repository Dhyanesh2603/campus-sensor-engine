from typing import Union
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundError
from app.core.response import success_response
from app.dependencies.database import get_db
from app.dependencies.redis import get_cooldown_manager, get_sliding_window
from app.redis.cooldown import CooldownManager
from app.redis.sliding_window import SlidingWindowManager
from app.repositories.reading_repository import ReadingRepository
from app.repositories.sensor_repository import SensorRepository
from app.schemas.sensor import (
    SensorReadingIn,
    SensorReadingResponse,
    SensorResponse,
)
from app.services.rule_cache_service import RuleCacheService
from app.services.sensor_ingestion_service import SensorIngestionService

router = APIRouter(tags=["Sensors & Ingestion"])


@router.post("/readings", status_code=status.HTTP_200_OK)
async def ingest_readings(
    payload: Union[SensorReadingIn, list[SensorReadingIn]],
    session: AsyncSession = Depends(get_db),
    sliding_window: SlidingWindowManager = Depends(get_sliding_window),
    cooldown_manager: CooldownManager = Depends(get_cooldown_manager),
):
    """
    Ingest single sensor reading or batch of readings.
    High-performance pipeline optimized for 10,000 readings/sec bursts.
    """
    readings = [payload] if isinstance(payload, SensorReadingIn) else payload

    ingestion_service = SensorIngestionService(
        session=session,
        sliding_window=sliding_window,
        cooldown_manager=cooldown_manager,
        rule_cache=RuleCacheService.get_instance(),
    )

    summary = await ingestion_service.ingest_readings(readings)
    return success_response(
        data=summary.model_dump(),
        message="Readings processed successfully",
        status_code=status.HTTP_200_OK,
    )


@router.get("/sensors", status_code=status.HTTP_200_OK)
async def list_sensors(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    sensor_type: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
):
    repo = SensorRepository(session)
    sensors = await repo.list_sensors(
        skip=skip,
        limit=limit,
        sensor_type=sensor_type,
        is_active=is_active,
    )
    data = [SensorResponse.model_validate(s).model_dump(mode="json") for s in sensors]
    return success_response(
        data=data,
        message=f"Retrieved {len(data)} sensors",
    )


@router.get("/sensors/{sensor_id}", status_code=status.HTTP_200_OK)
async def get_sensor(
    sensor_id: str,
    session: AsyncSession = Depends(get_db),
):
    repo = SensorRepository(session)
    sensor = await repo.get_by_id(sensor_id)
    if not sensor:
        raise NotFoundError(f"Sensor '{sensor_id}' not found")

    return success_response(
        data=SensorResponse.model_validate(sensor).model_dump(mode="json"),
        message="Sensor details retrieved",
    )


@router.get("/sensors/{sensor_id}/readings", status_code=status.HTTP_200_OK)
async def get_sensor_readings(
    sensor_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db),
):
    repo = ReadingRepository(session)
    readings = await repo.get_sensor_readings(sensor_id=sensor_id, limit=limit)
    data = [SensorReadingResponse.model_validate(r).model_dump(mode="json") for r in readings]
    return success_response(
        data=data,
        message=f"Retrieved {len(data)} historical readings",
    )
