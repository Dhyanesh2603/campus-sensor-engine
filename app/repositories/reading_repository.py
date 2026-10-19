from collections.abc import Sequence
from datetime import datetime
from typing import Any
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.sensor_reading import SensorReading
from app.repositories.base_repository import BaseRepository


class ReadingRepository(BaseRepository[SensorReading]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SensorReading, session)

    async def bulk_insert(self, reading_records: list[dict[str, Any]]) -> int:
        """
        Executes high-throughput bulk insert of sensor readings.
        """
        if not reading_records:
            return 0

        stmt = insert(SensorReading).values(reading_records)
        await self.session.execute(stmt)
        return len(reading_records)

    async def get_sensor_readings(
        self,
        sensor_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> Sequence[SensorReading]:
        query = select(SensorReading).where(SensorReading.sensor_id == sensor_id)
        if start_time:
            query = query.where(SensorReading.timestamp >= start_time)
        if end_time:
            query = query.where(SensorReading.timestamp <= end_time)
        query = query.order_by(SensorReading.timestamp.desc()).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
