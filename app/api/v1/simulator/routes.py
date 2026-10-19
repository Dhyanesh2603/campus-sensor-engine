from fastapi import APIRouter, Depends, Request, status
from app.core.response import success_response
from app.dependencies.auth import require_organizer
from app.models.user import User
from app.schemas.simulator import SimulatorStartRequest
from app.services.simulator_service import SimulatorManager

router = APIRouter(prefix="/simulator", tags=["Sensor Simulator"])


@router.post("/start", status_code=status.HTTP_200_OK)
async def start_simulator(
    data: SimulatorStartRequest,
    request: Request,
    current_user: User = Depends(require_organizer),
):
    manager = SimulatorManager.get_instance()
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else None

    # Derive current host URL for internal dispatch
    host_url = f"{request.url.scheme}://{request.url.netloc}/api/v1/readings"

    await manager.start(data, target_api_url=host_url, auth_token=token)
    return success_response(
        data=manager.get_status().model_dump(),
        message=f"Simulator started with {data.number_of_sensors} sensors for {data.duration_seconds}s",
    )


@router.post("/stop", status_code=status.HTTP_200_OK)
async def stop_simulator(
    current_user: User = Depends(require_organizer),
):
    manager = SimulatorManager.get_instance()
    await manager.stop()
    return success_response(
        data=manager.get_status().model_dump(),
        message="Simulator stopped",
    )


@router.get("/status", status_code=status.HTTP_200_OK)
async def get_simulator_status(
    current_user: User = Depends(require_organizer),
):
    manager = SimulatorManager.get_instance()
    return success_response(
        data=manager.get_status().model_dump(),
        message="Simulator status retrieved",
    )
