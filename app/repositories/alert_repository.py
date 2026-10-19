import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.alert import Alert
from app.repositories.base_repository import BaseRepository
from app.schemas.alert import AlertFilterQuery


class AlertRepository(BaseRepository[Alert]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Alert, session)

    async def get_by_id(self, alert_id: uuid.UUID) -> Alert | None:
        result = await self.session.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        return result.scalar_one_or_none()

    async def bulk_create_alerts(self, alert_records: list[dict[str, Any]]) -> list[Alert]:
        if not alert_records:
            return []

        # Return models for further downstream processing if needed
        alerts = [Alert(**record) for record in alert_records]
        self.session.add_all(alerts)
        await self.session.flush()
        return alerts

    async def list_alerts_paginated(
        self,
        filters: AlertFilterQuery,
    ) -> tuple[Sequence[Alert], int]:
        query = select(Alert)
        count_query = select(func.count(Alert.id))

        if filters.status:
            query = query.where(Alert.status == filters.status)
            count_query = count_query.where(Alert.status == filters.status)
        if filters.severity:
            query = query.where(Alert.severity == filters.severity)
            count_query = count_query.where(Alert.severity == filters.severity)
        if filters.sensor_id:
            query = query.where(Alert.sensor_id == filters.sensor_id)
            count_query = count_query.where(Alert.sensor_id == filters.sensor_id)
        if filters.rule_id:
            query = query.where(Alert.rule_id == filters.rule_id)
            count_query = count_query.where(Alert.rule_id == filters.rule_id)
        if filters.start_date:
            query = query.where(Alert.triggered_at >= filters.start_date)
            count_query = count_query.where(Alert.triggered_at >= filters.start_date)
        if filters.end_date:
            query = query.where(Alert.triggered_at <= filters.end_date)
            count_query = count_query.where(Alert.triggered_at <= filters.end_date)
        if filters.search:
            search_pattern = f"%{filters.search}%"
            search_clause = or_(
                Alert.sensor_id.ilike(search_pattern),
                Alert.severity.ilike(search_pattern),
                Alert.status.ilike(search_pattern),
            )
            query = query.where(search_clause)
            count_query = count_query.where(search_clause)

        # Sorting
        sort_column = getattr(Alert, filters.sort_by, Alert.created_at)
        if filters.sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Total count
        total_res = await self.session.execute(count_query)
        total: int = total_res.scalar() or 0

        # Pagination
        offset = (filters.page - 1) * filters.page_size
        query = query.offset(offset).limit(filters.page_size)

        result = await self.session.execute(query)
        items = result.scalars().all()
        return items, total

    async def acknowledge_alert(self, alert: Alert) -> Alert:
        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(alert)
        return alert

    async def resolve_alert(self, alert: Alert) -> Alert:
        alert.status = "RESOLVED"
        alert.resolved_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(alert)
        return alert
