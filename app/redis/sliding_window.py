import time
import uuid
from typing import Any
import redis.asyncio as aioredis
from app.config.settings import get_settings
from app.core.logging import get_logger

logger = get_logger("redis.sliding_window")
settings = get_settings()


class SlidingWindowManager:
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client
        self.max_retention = settings.SLIDING_WINDOW_MAX_RETENTION_SECONDS

    def _key(self, sensor_id: str, sensor_type: str) -> str:
        return f"sw:{sensor_id}:{sensor_type}"

    async def add_reading(
        self,
        sensor_id: str,
        sensor_type: str,
        timestamp: float,
        value: float,
    ) -> None:
        key = self._key(sensor_id, sensor_type)
        member = f"{timestamp}:{value}:{uuid.uuid4().hex[:8]}"
        cutoff = timestamp - self.max_retention

        pipe = self.redis.pipeline(transaction=False)
        pipe.zadd(key, {member: timestamp})
        pipe.zremrangebyscore(key, 0, cutoff)
        pipe.expire(key, self.max_retention + 60)
        await pipe.execute()

    async def add_readings_batch(
        self,
        readings: list[dict[str, Any]],
    ) -> None:
        if not readings:
            return

        pipe = self.redis.pipeline(transaction=False)
        keys_touched: set[str] = set()
        min_cutoff: float | None = None

        for r in readings:
            sid = r["sensor_id"]
            stype = r["sensor_type"]
            ts = r["timestamp"]
            val = r["value"]
            key = self._key(sid, stype)
            member = f"{ts}:{val}:{uuid.uuid4().hex[:8]}"
            pipe.zadd(key, {member: ts})
            keys_touched.add(key)
            cutoff = ts - self.max_retention
            if min_cutoff is None or cutoff < min_cutoff:
                min_cutoff = cutoff

        if min_cutoff is not None:
            for k in keys_touched:
                pipe.zremrangebyscore(k, 0, min_cutoff)
                pipe.expire(k, self.max_retention + 60)

        await pipe.execute()

    async def get_window_aggregation(
        self,
        sensor_id: str,
        sensor_type: str,
        window_seconds: int,
        aggregation: str,
        now_timestamp: float | None = None,
    ) -> float | None:
        """
        Calculates window aggregation (AVG, MIN, MAX, COUNT) over the specified window.
        """
        current_time = now_timestamp if now_timestamp is not None else time.time()
        start_time = current_time - window_seconds
        key = self._key(sensor_id, sensor_type)

        # Retrieve all elements in range [start_time, current_time]
        items = await self.redis.zrangebyscore(key, min=start_time, max=current_time)
        if not items:
            return None

        values: list[float] = []
        for item in items:
            try:
                # Format: timestamp:value:uuid
                parts = item.split(":")
                if len(parts) >= 2:
                    values.append(float(parts[1]))
            except (ValueError, IndexError):
                continue

        if not values:
            return None

        agg_upper = aggregation.upper()
        if agg_upper == "COUNT":
            return float(len(values))
        elif agg_upper == "AVG":
            return sum(values) / len(values)
        elif agg_upper == "MIN":
            return min(values)
        elif agg_upper == "MAX":
            return max(values)
        else:
            logger.error("unsupported_aggregation_requested", aggregation=aggregation)
            return None
