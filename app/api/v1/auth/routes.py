from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.response import success_response
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.auth import (
    RefreshTokenRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegisterRequest,
    session: AsyncSession = Depends(get_db),
):
    service = AuthService(session)
    user = await service.register(data)
    return success_response(
        data=user.model_dump(mode="json"),
        message="User registered successfully",
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/login", status_code=status.HTTP_200_OK)
async def login(
    data: UserLoginRequest,
    session: AsyncSession = Depends(get_db),
):
    service = AuthService(session)
    tokens = await service.login(data)
    return success_response(
        data=tokens.model_dump(),
        message="Authentication successful",
    )


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_tokens(
    data: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db),
):
    service = AuthService(session)
    tokens = await service.refresh_tokens(data)
    return success_response(
        data=tokens.model_dump(),
        message="Tokens refreshed successfully",
    )


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return success_response(
        data=UserResponse.model_validate(current_user).model_dump(mode="json"),
        message="Current user profile retrieved",
    )
