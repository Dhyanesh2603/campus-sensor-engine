from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from app.api.v1 import api_v1_router
from app.config.settings import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.response import success_response
from app.database.session import async_session_factory, engine
from app.middleware.exception_handler import register_exception_handlers
from app.middleware.logging_middleware import LoggingMiddleware
from app.redis.client import close_redis, ping_redis
from app.services.rule_cache_service import RuleCacheService

settings = get_settings()
setup_logging()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("app_starting", app_name=settings.APP_NAME, environment=settings.ENVIRONMENT)

    # Pre-warm Redis and Rule Cache
    redis_healthy = await ping_redis()
    logger.info("redis_health_checked", healthy=redis_healthy)

    try:
        async with async_session_factory() as session:
            await RuleCacheService.get_instance().refresh(session)
            logger.info("rule_cache_prewarmed")
    except Exception as exc:
        logger.warning("rule_cache_prewarm_deferred", error=str(exc))

    yield

    logger.info("app_shutting_down")
    await close_redis()
    await engine.dispose()
    logger.info("database_and_redis_connections_closed")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise-grade IoT campus sensor ingestion, real-time sliding window rule evaluation, and alert management engine.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Correlation and Performance Middleware
app.add_middleware(LoggingMiddleware)

# Global Exception Handlers
register_exception_handlers(app)

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Include API Routers
app.include_router(api_v1_router)

# Mount Frontend Dashboard
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/dashboard", StaticFiles(directory=frontend_dir, html=True), name="dashboard")

    @app.get("/dashboard", include_in_schema=False)
    async def get_dashboard():
        return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.get("/", status_code=status.HTTP_200_OK, tags=["System"])
async def root():
    return success_response(
        data={
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "docs": "/docs",
            "dashboard": "/dashboard",
        },
        message="Campus Sensor Monitoring & Alert Engine API",
    )


@app.get("/health", status_code=status.HTTP_200_OK, tags=["System"])
@app.get("/api/v1/health", status_code=status.HTTP_200_OK, tags=["System"])
async def health_check():
    redis_ok = await ping_redis()

    db_ok = False
    try:
        async with async_session_factory() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False

    overall_healthy = redis_ok and db_ok
    status_code = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return success_response(
        data={
            "status": "healthy" if overall_healthy else "degraded",
            "database": "connected" if db_ok else "disconnected",
            "redis": "connected" if redis_ok else "disconnected",
        },
        message="Service health status",
        status_code=status_code,
    )


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Production API with JWT Authentication, Batch Ingestion, Sliding Windows, and Alert Rules",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
