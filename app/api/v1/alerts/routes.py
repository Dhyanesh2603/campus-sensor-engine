import uuid
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.response import success_response
from app.dependencies.auth import get_current_user, require_organizer
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.alert import AlertFilterQuery, AlertSeverity, AlertStatus
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["Alerts Management"])


@router.get("", status_code=status.HTTP_200_OK)
async def list_alerts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    status_filter: AlertStatus | None = Query(default=None, alias="status"),
    severity: AlertSeverity | None = Query(default=None),
    sensor_id: str | None = Query(default=None),
    rule_id: uuid.UUID | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = AlertService(session)
    filters = AlertFilterQuery(
        page=page,
        page_size=page_size,
        status=status_filter,
        severity=severity,
        sensor_id=sensor_id,
        rule_id=rule_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    result = await service.list_alerts(filters)
    return success_response(
        data=result.model_dump(mode="json"),
        message=f"Retrieved {len(result.items)} alerts (total: {result.total})",
    )


@router.get("/{alert_id}", status_code=status.HTTP_200_OK)
async def get_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = AlertService(session)
    alert = await service.get_alert(alert_id)
    return success_response(
        data=alert.model_dump(mode="json"),
        message="Alert retrieved successfully",
    )


@router.patch("/{alert_id}/acknowledge", status_code=status.HTTP_200_OK)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(require_organizer),
    session: AsyncSession = Depends(get_db),
):
    service = AlertService(session)
    alert = await service.acknowledge_alert(alert_id)
    return success_response(
        data=alert.model_dump(mode="json"),
        message="Alert marked as ACKNOWLEDGED",
    )


@router.patch("/{alert_id}/resolve", status_code=status.HTTP_200_OK)
async def resolve_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(require_organizer),
    session: AsyncSession = Depends(get_db),
):
    service = AlertService(session)
    alert = await service.resolve_alert(alert_id)
    return success_response(
        data=alert.model_dump(mode="json"),
        message="Alert marked as RESOLVED",
    )


@router.delete("/{alert_id}", status_code=status.HTTP_200_OK)
async def delete_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(require_organizer),
    session: AsyncSession = Depends(get_db),
):
    service = AlertService(session)
    await service.delete_alert(alert_id)
    return success_response(
        data={"deleted_id": str(alert_id)},
        message="Alert deleted successfully",
    )
