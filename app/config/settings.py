from functools import lru_cache
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = False
    APP_NAME: str = "Campus Sensor Monitoring & Alert Engine"
    APP_VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # PostgreSQL Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/campus_sensors",
        description="Async SQLAlchemy database connection URI",
    )
    DATABASE_POOL_SIZE: int = 25
    DATABASE_MAX_OVERFLOW: int = 50
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800

    # Redis Cache & Sliding Windows
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URI",
    )
    REDIS_MAX_CONNECTIONS: int = 100

    # JWT Authentication
    JWT_SECRET: str = "super-secret-production-key-change-me-at-all-costs-32chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Ingestion & Alert Engine Tuning
    MAX_BATCH_SIZE: int = 10000
    DEFAULT_ALERT_COOLDOWN_SECONDS: int = 300
    SLIDING_WINDOW_MAX_RETENTION_SECONDS: int = 3600
    RULE_CACHE_TTL_SECONDS: int = 60


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
