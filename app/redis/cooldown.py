import redis.asyncio as aioredis
from app.core.logging import get_logger

logger = get_logger("redis.cooldown")


class CooldownManager:
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    def _key(self, rule_id: str, sensor_id: str) -> str:
        return f"alert:cooldown:{rule_id}:{sensor_id}"

    async def is_in_cooldown(self, rule_id: str, sensor_id: str) -> bool:
        key = self._key(rule_id, sensor_id)
        exists = await self.redis.exists(key)
        return bool(exists)

    async def acquire_cooldown_lock(
        self,
        rule_id: str,
        sensor_id: str,
        cooldown_seconds: int = 300,
    ) -> bool:
        """
        Atomically checks if an alert cooldown is active.
        If active, returns False (alert suppressed).
        If not active, sets cooldown key with TTL and returns True (alert allowed).
        """
        key = self._key(rule_id, sensor_id)
        # SET key 1 EX cooldown_seconds NX (only set if not exists)
        acquired = await self.redis.set(key, "1", ex=cooldown_seconds, nx=True)
        if acquired:
            logger.debug(
                "cooldown_lock_acquired",
                rule_id=rule_id,
                sensor_id=sensor_id,
                cooldown_seconds=cooldown_seconds,
            )
            return True
        else:
            logger.debug(
                "cooldown_suppression_active",
                rule_id=rule_id,
                sensor_id=sensor_id,
            )
            return False

    async def clear_cooldown(self, rule_id: str, sensor_id: str) -> None:
        key = self._key(rule_id, sensor_id)
        await self.redis.delete(key)
