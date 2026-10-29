import time
from typing import Any


class InMemoryRedisPipeline:
    def __init__(self, in_memory_redis: "InMemoryRedis") -> None:
        self.in_memory_redis = in_memory_redis
        self.commands: list[tuple[str, tuple, dict[str, Any]]] = []

    def zadd(self, key: str, mapping: dict[str, float]) -> "InMemoryRedisPipeline":
        self.commands.append(("zadd", (key, mapping), {}))
        return self

    def zremrangebyscore(self, key: str, min_val: float, max_val: float) -> "InMemoryRedisPipeline":
        self.commands.append(("zremrangebyscore", (key, min_val, max_val), {}))
        return self

    def expire(self, key: str, seconds: int) -> "InMemoryRedisPipeline":
        self.commands.append(("expire", (key, seconds), {}))
        return self

    async def execute(self) -> list[Any]:
        results = []
        for cmd, args, kwargs in self.commands:
            method = getattr(self.in_memory_redis, cmd)
            res = await method(*args, **kwargs)
            results.append(res)
        self.commands.clear()
        return results


class InMemoryRedis:
    """
    In-memory fallback Redis engine for standalone local execution
    when an external Redis service is not provisioned.
    """
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.expirations: dict[str, float] = {}
        self.zsets: dict[str, dict[str, float]] = {}

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        if key in self.expirations and time.time() > self.expirations[key]:
            del self.kv[key]
            del self.expirations[key]
            return None
        return self.kv.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool:
        if nx and await self.exists(key):
            return False
        self.kv[key] = value
        if ex is not None:
            self.expirations[key] = time.time() + ex
        elif key in self.expirations:
            del self.expirations[key]
        return True

    async def expire(self, key: str, seconds: int) -> bool:
        if key in self.kv or key in self.zsets:
            self.expirations[key] = time.time() + seconds
            return True
        return False

    async def exists(self, key: str) -> int:
        if key in self.expirations and time.time() > self.expirations[key]:
            self.kv.pop(key, None)
            self.expirations.pop(key, None)
            return 0
        return 1 if (key in self.kv or key in self.zsets) else 0

    async def delete(self, key: str) -> int:
        deleted = 0
        if key in self.kv:
            del self.kv[key]
            deleted = 1
        if key in self.expirations:
            del self.expirations[key]
        if key in self.zsets:
            del self.zsets[key]
            deleted = 1
        return deleted

    def pipeline(self, transaction: bool = False) -> InMemoryRedisPipeline:
        return InMemoryRedisPipeline(self)

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        z = self.zsets.setdefault(key, {})
        count = 0
        for member, score in mapping.items():
            if member not in z:
                count += 1
            z[member] = float(score)
        return count

    async def zremrangebyscore(self, key: str, min_val: float, max_val: float) -> int:
        if key not in self.zsets:
            return 0
        z = self.zsets[key]
        to_del = [m for m, s in z.items() if min_val <= s <= max_val]
        for m in to_del:
            del z[m]
        return len(to_del)

    async def zrangebyscore(self, key: str, min: float, max: float) -> list[str]:
        if key not in self.zsets:
            return []
        z = self.zsets[key]
        matching = [m for m, s in z.items() if min <= s <= max]
        matching.sort(key=lambda m: z[m])
        return matching
