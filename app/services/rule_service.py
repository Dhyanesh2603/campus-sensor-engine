import uuid
from collections.abc import Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.alert_rule import AlertRule
from app.repositories.rule_repository import RuleRepository
from app.schemas.rule import RuleCreateRequest, RuleResponse, RuleUpdateRequest, WINDOW_MAP
from app.services.rule_cache_service import RuleCacheService

logger = get_logger("services.rule")


class RuleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.rule_repo = RuleRepository(session)
        self.rule_cache = RuleCacheService.get_instance()

    async def create_rule(self, data: RuleCreateRequest) -> RuleResponse:
        window_seconds = None
        if data.window:
            window_seconds = WINDOW_MAP.get(data.window.strip().lower(), 300)

        rule = AlertRule(
            name=data.name,
            description=data.description,
            sensor_type=data.sensor_type,
            rule_type=data.rule_type,
            operator=data.operator,
            threshold=data.threshold,
            aggregation=data.aggregation,
            window=data.window,
            window_seconds=window_seconds,
            cooldown_seconds=data.cooldown_seconds,
            enabled=data.enabled,
            severity=data.severity,
        )
        created = await self.rule_repo.create(rule)
        await self.session.refresh(created)
        self.rule_cache.invalidate()

        logger.info(
            "rule_created",
            rule_id=str(created.id),
            name=created.name,
            sensor_type=created.sensor_type,
            rule_type=created.rule_type,
        )
        return RuleResponse.model_validate(created)

    async def get_rule(self, rule_id: uuid.UUID) -> RuleResponse:
        rule = await self.rule_repo.get_by_id(rule_id)
        if not rule:
            raise NotFoundError(f"Alert rule with ID {rule_id} not found")
        return RuleResponse.model_validate(rule)

    async def list_rules(
        self,
        sensor_type: str | None = None,
        enabled: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[RuleResponse]:
        rules = await self.rule_repo.list_rules(
            sensor_type=sensor_type,
            enabled=enabled,
            skip=skip,
            limit=limit,
        )
        return [RuleResponse.model_validate(r) for r in rules]

    async def update_rule(self, rule_id: uuid.UUID, data: RuleUpdateRequest) -> RuleResponse:
        rule = await self.rule_repo.get_by_id(rule_id)
        if not rule:
            raise NotFoundError(f"Alert rule with ID {rule_id} not found")

        update_dict = data.model_dump(exclude_unset=True)
        if "window" in update_dict and update_dict["window"]:
            update_dict["window_seconds"] = WINDOW_MAP.get(
                update_dict["window"].strip().lower(), 300
            )

        for key, value in update_dict.items():
            setattr(rule, key, value)

        await self.session.flush()
        await self.session.refresh(rule)
        self.rule_cache.invalidate()

        logger.info("rule_updated", rule_id=str(rule.id))
        return RuleResponse.model_validate(rule)

    async def delete_rule(self, rule_id: uuid.UUID) -> None:
        rule = await self.rule_repo.get_by_id(rule_id)
        if not rule:
            raise NotFoundError(f"Alert rule with ID {rule_id} not found")

        await self.rule_repo.delete(rule)
        self.rule_cache.invalidate()
        logger.info("rule_deleted", rule_id=str(rule_id))

    async def set_rule_enabled(self, rule_id: uuid.UUID, enabled: bool) -> RuleResponse:
        rule = await self.rule_repo.get_by_id(rule_id)
        if not rule:
            raise NotFoundError(f"Alert rule with ID {rule_id} not found")

        rule.enabled = enabled
        await self.session.flush()
        await self.session.refresh(rule)
        self.rule_cache.invalidate()
        logger.info("rule_enabled_status_updated", rule_id=str(rule.id), enabled=enabled)
        return RuleResponse.model_validate(rule)
