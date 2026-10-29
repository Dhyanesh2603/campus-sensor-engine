from typing import Any
import redis.asyncio as aioredis
from app.config.settings import get_settings
from app.core.logging import get_logger
from app.redis.in_memory import InMemoryRedis

logger = get_logger("redis.client")
settings = get_settings()

_redis_pool: aioredis.ConnectionPool | None = None
_in_memory_instance: InMemoryRedis | None = None


def get_redis_pool() -> aioredis.ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )
    return _redis_pool


async def get_redis_client() -> Any:
    global _in_memory_instance
    if _in_memory_instance is not None:
        return _in_memory_instance

    try:
        pool = get_redis_pool()
        client = aioredis.Redis(connection_pool=pool)
        await client.ping()
        return client
    except Exception as exc:
        logger.warning("external_redis_unavailable_fallback_to_in_memory", error=str(exc))
        if _in_memory_instance is None:
            _in_memory_instance = InMemoryRedis()
        return _in_memory_instance


async def close_redis() -> None:
    global _redis_pool, _in_memory_instance
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None
        logger.info("redis_pool_disconnected")
    _in_memory_instance = None


async def ping_redis() -> bool:
    try:
        client = await get_redis_client()
        return bool(await client.ping())
    except Exception as exc:
        logger.warning("redis_ping_failed", error=str(exc))
        return False
