from fastapi import APIRouter
from app.api.v1.alerts.routes import router as alerts_router
from app.api.v1.auth.routes import router as auth_router
from app.api.v1.rules.routes import router as rules_router
from app.api.v1.sensors.routes import router as sensors_router
from app.api.v1.simulator.routes import router as simulator_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(sensors_router)
api_v1_router.include_router(rules_router)
api_v1_router.include_router(alerts_router)
api_v1_router.include_router(simulator_router)
