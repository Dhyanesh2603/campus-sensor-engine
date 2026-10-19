import redis.asyncio as aioredis
from fastapi import Depends
from app.redis.client import get_redis_client
from app.redis.cooldown import CooldownManager
from app.redis.sliding_window import SlidingWindowManager


async def get_redis() -> aioredis.Redis:
    return await get_redis_client()


def get_sliding_window(
    redis: aioredis.Redis = Depends(get_redis),
) -> SlidingWindowManager:
    return SlidingWindowManager(redis)


def get_cooldown_manager(
    redis: aioredis.Redis = Depends(get_redis),
) -> CooldownManager:
    return CooldownManager(redis)
