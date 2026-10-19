import asyncio
import time
from collections.abc import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.database.base import Base
from app.dependencies.database import get_db
from app.dependencies.redis import get_redis
from app.main import app
from app.services.rule_cache_service import RuleCacheService

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


class FakeRedisPipeline:
    def __init__(self, fake_redis: "FakeRedis") -> None:
        self.fake_redis = fake_redis
        self.commands: list[tuple[str, tuple, dict]] = []

    def zadd(self, key: str, mapping: dict[str, float]) -> "FakeRedisPipeline":
        self.commands.append(("zadd", (key, mapping), {}))
        return self

    def zremrangebyscore(self, key: str, min_val: float, max_val: float) -> "FakeRedisPipeline":
        self.commands.append(("zremrangebyscore", (key, min_val, max_val), {}))
        return self

    def expire(self, key: str, seconds: int) -> "FakeRedisPipeline":
        self.commands.append(("expire", (key, seconds), {}))
        return self

    async def execute(self) -> list:
        results = []
        for cmd, args, kwargs in self.commands:
            method = getattr(self.fake_redis, cmd)
            res = await method(*args, **kwargs)
            results.append(res)
        self.commands.clear()
        return results


class FakeRedis:
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

    def pipeline(self, transaction: bool = False) -> FakeRedisPipeline:
        return FakeRedisPipeline(self)

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

    async def expire(self, key: str, seconds: int) -> bool:
        self.expirations[key] = time.time() + seconds
        return True


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession, fake_redis: FakeRedis) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    # Invalidate rule cache for isolated test execution
    RuleCacheService.get_instance(fake_redis).invalidate()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
