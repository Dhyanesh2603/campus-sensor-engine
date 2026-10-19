import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.response import success_response
from app.dependencies.auth import get_current_user, require_organizer
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.rule import RuleCreateRequest, RuleUpdateRequest
from app.services.rule_service import RuleService

router = APIRouter(prefix="/rules", tags=["Alert Rules"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_rule(
    data: RuleCreateRequest,
    current_user: User = Depends(require_organizer),
    session: AsyncSession = Depends(get_db),
):
    service = RuleService(session)
    rule = await service.create_rule(data)
    return success_response(
        data=rule.model_dump(mode="json"),
        message="Alert rule created successfully",
        status_code=status.HTTP_201_CREATED,
    )


@router.get("", status_code=status.HTTP_200_OK)
async def list_rules(
    sensor_type: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = RuleService(session)
    rules = await service.list_rules(
        sensor_type=sensor_type,
        enabled=enabled,
        skip=skip,
        limit=limit,
    )
    data = [r.model_dump(mode="json") for r in rules]
    return success_response(
        data=data,
        message=f"Retrieved {len(data)} rules",
    )


@router.get("/{rule_id}", status_code=status.HTTP_200_OK)
async def get_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = RuleService(session)
    rule = await service.get_rule(rule_id)
    return success_response(
        data=rule.model_dump(mode="json"),
        message="Alert rule retrieved successfully",
    )


@router.put("/{rule_id}", status_code=status.HTTP_200_OK)
async def update_rule(
    rule_id: uuid.UUID,
    data: RuleUpdateRequest,
    current_user: User = Depends(require_organizer),
    session: AsyncSession = Depends(get_db),
):
    service = RuleService(session)
    rule = await service.update_rule(rule_id, data)
    return success_response(
        data=rule.model_dump(mode="json"),
        message="Alert rule updated successfully",
    )


@router.delete("/{rule_id}", status_code=status.HTTP_200_OK)
async def delete_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(require_organizer),
    session: AsyncSession = Depends(get_db),
):
    service = RuleService(session)
    await service.delete_rule(rule_id)
    return success_response(
        data={"deleted_id": str(rule_id)},
        message="Alert rule deleted successfully",
    )


@router.patch("/{rule_id}/enable", status_code=status.HTTP_200_OK)
async def enable_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(require_organizer),
    session: AsyncSession = Depends(get_db),
):
    service = RuleService(session)
    rule = await service.set_rule_enabled(rule_id, enabled=True)
    return success_response(
        data=rule.model_dump(mode="json"),
        message="Alert rule enabled successfully",
    )


@router.patch("/{rule_id}/disable", status_code=status.HTTP_200_OK)
async def disable_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(require_organizer),
    session: AsyncSession = Depends(get_db),
):
    service = RuleService(session)
    rule = await service.set_rule_enabled(rule_id, enabled=False)
    return success_response(
        data=rule.model_dump(mode="json"),
        message="Alert rule disabled successfully",
    )
