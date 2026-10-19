import asyncio
import time
from typing import Any
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.settings import get_settings
from app.core.logging import get_logger
from app.models.alert_rule import AlertRule
from app.repositories.rule_repository import RuleRepository

logger = get_logger("services.rule_cache")
settings = get_settings()


class RuleCacheService:
    _instance: "RuleCacheService | None" = None
    _lock = asyncio.Lock()

    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self.redis = redis_client
        self._rules_by_type: dict[str, list[AlertRule]] = {}
        self._all_enabled_rules: list[AlertRule] = []
        self._last_loaded_at: float = 0.0
        self.ttl = settings.RULE_CACHE_TTL_SECONDS

    @classmethod
    def get_instance(cls, redis_client: aioredis.Redis | None = None) -> "RuleCacheService":
        if cls._instance is None:
            cls._instance = cls(redis_client)
        return cls._instance

    def is_stale(self) -> bool:
        return (time.time() - self._last_loaded_at) > self.ttl

    async def get_rules_for_sensor_type(
        self,
        sensor_type: str,
        session: AsyncSession,
    ) -> list[AlertRule]:
        if self.is_stale() or not self._all_enabled_rules:
            await self.refresh(session)
        return self._rules_by_type.get(sensor_type, [])

    async def get_all_rules(self, session: AsyncSession) -> list[AlertRule]:
        if self.is_stale() or not self._all_enabled_rules:
            await self.refresh(session)
        return self._all_enabled_rules

    async def refresh(self, session: AsyncSession) -> None:
        async with self._lock:
            # Double-check inside lock
            if not self.is_stale() and self._all_enabled_rules:
                return

            repo = RuleRepository(session)
            enabled_rules = await repo.get_all_enabled_rules()

            rules_by_type: dict[str, list[AlertRule]] = {}
            for rule in enabled_rules:
                rules_by_type.setdefault(rule.sensor_type, []).append(rule)

            self._all_enabled_rules = list(enabled_rules)
            self._rules_by_type = rules_by_type
            self._last_loaded_at = time.time()

            logger.info(
                "rule_cache_refreshed",
                total_enabled_rules=len(self._all_enabled_rules),
                sensor_types=list(rules_by_type.keys()),
            )

    def invalidate(self) -> None:
        """
        Immediately forces a reload on the next read.
        """
        self._last_loaded_at = 0.0
        logger.info("rule_cache_invalidated")
