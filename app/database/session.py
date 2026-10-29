from collections.abc import AsyncGenerator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.config.settings import get_settings
from app.core.logging import get_logger

logger = get_logger("database.session")
settings = get_settings()

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db_connection() -> bool:
    """
    Initializes database connectivity. If PostgreSQL is unreachable,
    gracefully falls back to local SQLite with automatic schema creation and seeding.
    """
    global engine, async_session_factory
    from app.database.base import Base

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("database_connected", url=settings.DATABASE_URL.split("@")[-1])
        return True
    except Exception as exc:
        logger.warning("external_database_unavailable_fallback_to_sqlite", error=str(exc))
        sqlite_url = "sqlite+aiosqlite:///./campus_sensors.db"
        engine = create_async_engine(
            sqlite_url,
            echo=False,
            connect_args={"timeout": 30.0},
        )
        async_session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        from sqlalchemy import event
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

        async with engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            await conn.execute(text("PRAGMA busy_timeout=30000"))
            await conn.run_sync(Base.metadata.create_all)
        logger.info("sqlite_fallback_initialized", database_file="./campus_sensors.db")

        # Seed initial organizer and rules if empty
        async with async_session_factory() as session:
            await seed_default_data(session)

        return True


async def seed_default_data(session: AsyncSession) -> None:
    """
    Seeds default organizer user and initial alert rules into standalone SQLite database.
    """
    try:
        from app.core.security import hash_password
        from app.models.alert_rule import AlertRule
        from app.models.user import User

        # 1. Organizer account
        user_res = await session.execute(select(User).where(User.email == "organizer@campus.edu"))
        if not user_res.scalar_one_or_none():
            organizer = User(
                email="organizer@campus.edu",
                hashed_password=hash_password("Password123!"),
                full_name="Lead Campus Organizer",
                role="organizer",
                is_active=True,
            )
            session.add(organizer)

        # 2. Default Rules
        rules_res = await session.execute(select(AlertRule))
        if not rules_res.scalars().first():
            default_rules = [
                AlertRule(
                    name="Critical Temperature Spike",
                    sensor_type="temperature",
                    rule_type="threshold",
                    operator=">",
                    threshold=35.0,
                    severity="CRITICAL",
                    cooldown_seconds=120,
                    enabled=True,
                ),
                AlertRule(
                    name="High Occupancy Warning",
                    sensor_type="occupancy",
                    rule_type="threshold",
                    operator=">=",
                    threshold=300.0,
                    severity="HIGH",
                    cooldown_seconds=180,
                    enabled=True,
                ),
                AlertRule(
                    name="Poor Air Quality Rolling 5m",
                    sensor_type="air_quality",
                    rule_type="window",
                    aggregation="AVG",
                    window="5m",
                    operator=">",
                    threshold=150.0,
                    severity="HIGH",
                    cooldown_seconds=300,
                    enabled=True,
                ),
            ]
            session.add_all(default_rules)

        await session.commit()
        logger.info("default_data_seeded_successfully")
    except Exception as exc:
        logger.warning("default_data_seeding_skipped", error=str(exc))
        await session.rollback()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
