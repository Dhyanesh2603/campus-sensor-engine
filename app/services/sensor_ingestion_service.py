import time
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger
from app.redis.cooldown import CooldownManager
from app.redis.sliding_window import SlidingWindowManager
from app.repositories.alert_repository import AlertRepository
from app.repositories.reading_repository import ReadingRepository
from app.repositories.sensor_repository import SensorRepository
from app.schemas.sensor import IngestionSummary, SensorReadingIn
from app.services.rule_cache_service import RuleCacheService
from app.services.rule_evaluation_engine import RuleEvaluationEngine

logger = get_logger("services.ingestion")

# Cache to avoid repeated DB lookups for already-known sensor IDs
_known_sensors_cache: set[str] = set()


class SensorIngestionService:
    def __init__(
        self,
        session: AsyncSession,
        sliding_window: SlidingWindowManager,
        cooldown_manager: CooldownManager,
        rule_cache: RuleCacheService,
    ) -> None:
        self.session = session
        self.sensor_repo = SensorRepository(session)
        self.reading_repo = ReadingRepository(session)
        self.alert_repo = AlertRepository(session)
        self.sliding_window = sliding_window
        self.cooldown_manager = cooldown_manager
        self.rule_cache = rule_cache
        self.rule_engine = RuleEvaluationEngine(sliding_window, cooldown_manager)

    async def ingest_readings(
        self,
        readings: list[SensorReadingIn],
    ) -> IngestionSummary:
        start_time = time.perf_counter()
        total_received = len(readings)

        if not readings:
            return IngestionSummary(
                total_received=0,
                ingested_count=0,
                failed_count=0,
                alerts_triggered=0,
                duration_ms=0.0,
            )

        # 1. Identify any new sensors to ensure registration
        global _known_sensors_cache
        sensor_records_to_ensure: list[dict[str, str]] = []
        for r in readings:
            if r.sensor_id not in _known_sensors_cache:
                sensor_records_to_ensure.append({
                    "id": r.sensor_id,
                    "name": r.sensor_id,
                    "sensor_type": r.sensor_type,
                })

        if sensor_records_to_ensure:
            await self.sensor_repo.ensure_sensors_exist(sensor_records_to_ensure)
            for s in sensor_records_to_ensure:
                _known_sensors_cache.add(s["id"])

        # 2. Prepare bulk insert records for PostgreSQL
        reading_dicts: list[dict[str, Any]] = []
        redis_batch: list[dict[str, Any]] = []

        for r in readings:
            ts = r.timestamp if r.timestamp.tzinfo else r.timestamp.replace(tzinfo=timezone.utc)
            reading_dicts.append({
                "sensor_id": r.sensor_id,
                "sensor_type": r.sensor_type,
                "value": r.value,
                "timestamp": ts,
            })
            redis_batch.append({
                "sensor_id": r.sensor_id,
                "sensor_type": r.sensor_type,
                "value": r.value,
                "timestamp": ts.timestamp(),
            })

        # Bulk store readings
        ingested_count = await self.reading_repo.bulk_insert(reading_dicts)

        # 3. Update Redis sliding windows in pipeline
        await self.sliding_window.add_readings_batch(redis_batch)

        # 4. Evaluate alert rules
        alerts_to_persist: list[dict[str, Any]] = []
        sensor_types_in_batch = {r.sensor_type for r in readings}

        # Pre-fetch rules for relevant sensor types from cache
        rules_map = {}
        for st in sensor_types_in_batch:
            rules_map[st] = await self.rule_cache.get_rules_for_sensor_type(st, self.session)

        # Evaluate readings
        for r in readings:
            rules_for_type = rules_map.get(r.sensor_type, [])
            if not rules_for_type:
                continue

            ts = r.timestamp if r.timestamp.tzinfo else r.timestamp.replace(tzinfo=timezone.utc)
            alerts = await self.rule_engine.evaluate_reading(
                sensor_id=r.sensor_id,
                sensor_type=r.sensor_type,
                value=r.value,
                timestamp=ts,
                rules=rules_for_type,
            )
            alerts_to_persist.extend(alerts)

        # 5. Persist triggered alerts
        if alerts_to_persist:
            await self.alert_repo.bulk_create_alerts(alerts_to_persist)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "readings_batch_ingested",
            received=total_received,
            ingested=ingested_count,
            alerts_triggered=len(alerts_to_persist),
            duration_ms=duration_ms,
        )

        return IngestionSummary(
            total_received=total_received,
            ingested_count=ingested_count,
            failed_count=0,
            alerts_triggered=len(alerts_to_persist),
            duration_ms=duration_ms,
        )
