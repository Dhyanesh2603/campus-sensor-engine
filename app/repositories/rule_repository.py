import uuid
from collections.abc import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.alert_rule import AlertRule
from app.repositories.base_repository import BaseRepository


class RuleRepository(BaseRepository[AlertRule]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AlertRule, session)

    async def get_by_id(self, rule_id: uuid.UUID) -> AlertRule | None:
        result = await self.session.execute(
            select(AlertRule).where(AlertRule.id == rule_id)
        )
        return result.scalar_one_or_none()

    async def list_rules(
        self,
        sensor_type: str | None = None,
        enabled: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[AlertRule]:
        query = select(AlertRule)
        if sensor_type:
            query = query.where(AlertRule.sensor_type == sensor_type)
        if enabled is not None:
            query = query.where(AlertRule.enabled == enabled)
        query = query.order_by(AlertRule.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_all_enabled_rules(self) -> Sequence[AlertRule]:
        result = await self.session.execute(
            select(AlertRule).where(AlertRule.enabled == True)  # noqa: E712
        )
        return result.scalars().all()
