import math
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.alert import Alert
from app.repositories.alert_repository import AlertRepository
from app.schemas.alert import AlertFilterQuery, AlertResponse, PaginatedAlertsResponse

logger = get_logger("services.alert")


class AlertService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.alert_repo = AlertRepository(session)

    async def get_alert(self, alert_id: uuid.UUID) -> AlertResponse:
        alert = await self.alert_repo.get_by_id(alert_id)
        if not alert:
            raise NotFoundError(f"Alert with ID {alert_id} not found")
        return AlertResponse.model_validate(alert)

    async def list_alerts(self, filters: AlertFilterQuery) -> PaginatedAlertsResponse:
        items, total = await self.alert_repo.list_alerts_paginated(filters)
        total_pages = math.ceil(total / filters.page_size) if total > 0 else 0
        return PaginatedAlertsResponse(
            items=[AlertResponse.model_validate(a) for a in items],
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=total_pages,
        )

    async def acknowledge_alert(self, alert_id: uuid.UUID) -> AlertResponse:
        alert = await self.alert_repo.get_by_id(alert_id)
        if not alert:
            raise NotFoundError(f"Alert with ID {alert_id} not found")

        updated = await self.alert_repo.acknowledge_alert(alert)
        logger.info("alert_acknowledged", alert_id=str(alert_id))
        return AlertResponse.model_validate(updated)

    async def resolve_alert(self, alert_id: uuid.UUID) -> AlertResponse:
        alert = await self.alert_repo.get_by_id(alert_id)
        if not alert:
            raise NotFoundError(f"Alert with ID {alert_id} not found")

        updated = await self.alert_repo.resolve_alert(alert)
        logger.info("alert_resolved", alert_id=str(alert_id))
        return AlertResponse.model_validate(updated)

    async def delete_alert(self, alert_id: uuid.UUID) -> None:
        alert = await self.alert_repo.get_by_id(alert_id)
        if not alert:
            raise NotFoundError(f"Alert with ID {alert_id} not found")

        await self.alert_repo.delete(alert)
        logger.info("alert_deleted", alert_id=str(alert_id))
