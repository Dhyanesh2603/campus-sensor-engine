from typing import Any
import redis.asyncio as aioredis
from app.config.settings import get_settings
from app.core.logging import get_logger

logger = get_logger("redis.client")
settings = get_settings()

_redis_pool: aioredis.ConnectionPool | None = None


def get_redis_pool() -> aioredis.ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )
    return _redis_pool


async def get_redis_client() -> aioredis.Redis:
    pool = get_redis_pool()
    return aioredis.Redis(connection_pool=pool)


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None
        logger.info("redis_pool_disconnected")


async def ping_redis() -> bool:
    try:
        client = await get_redis_client()
        return bool(await client.ping())
    except Exception as exc:
        logger.warning("redis_ping_failed", error=str(exc))
        return False
