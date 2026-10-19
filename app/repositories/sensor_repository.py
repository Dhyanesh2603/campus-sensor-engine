from collections.abc import Sequence
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.sensor import Sensor
from app.repositories.base_repository import BaseRepository


class SensorRepository(BaseRepository[Sensor]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Sensor, session)

    async def get_by_id(self, sensor_id: str) -> Sensor | None:
        result = await self.session.execute(
            select(Sensor).where(Sensor.id == sensor_id)
        )
        return result.scalar_one_or_none()

    async def list_sensors(
        self,
        skip: int = 0,
        limit: int = 100,
        sensor_type: str | None = None,
        is_active: bool | None = None,
    ) -> Sequence[Sensor]:
        query = select(Sensor)
        if sensor_type:
            query = query.where(Sensor.sensor_type == sensor_type)
        if is_active is not None:
            query = query.where(Sensor.is_active == is_active)
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def ensure_sensors_exist(self, sensor_records: list[dict[str, str]]) -> None:
        """
        Idempotent bulk registration of sensors using ON CONFLICT DO NOTHING.
        """
        if not sensor_records:
            return

        # Deduplicate records by sensor_id
        unique_sensors: dict[str, dict[str, str]] = {}
        for s in sensor_records:
            sid = s["id"]
            if sid not in unique_sensors:
                unique_sensors[sid] = {
                    "id": sid,
                    "name": s.get("name") or sid,
                    "sensor_type": s["sensor_type"],
                    "is_active": True,
                }

        records_to_insert = list(unique_sensors.values())
        dialect = self.session.bind.dialect.name if self.session.bind else "postgresql"

        if dialect == "postgresql":
            stmt = pg_insert(Sensor).values(records_to_insert)
            stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
            await self.session.execute(stmt)
        else:
            # Fallback for SQLite in tests
            for record in records_to_insert:
                existing = await self.get_by_id(record["id"])
                if not existing:
                    new_sensor = Sensor(
                        id=record["id"],
                        name=record["name"],
                        sensor_type=record["sensor_type"],
                        is_active=True,
                    )
                    self.session.add(new_sensor)
            await self.session.flush()
