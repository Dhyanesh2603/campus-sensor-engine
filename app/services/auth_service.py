import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.settings import get_settings
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.security import create_jwt_token, decode_jwt_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

logger = get_logger("services.auth")
settings = get_settings()


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.user_repo = UserRepository(session)

    async def register(self, data: UserRegisterRequest) -> UserResponse:
        existing = await self.user_repo.get_by_email(data.email)
        if existing:
            raise ConflictError(f"User with email '{data.email}' already exists")

        user = User(
            email=data.email.lower().strip(),
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            role=data.role,
            is_active=True,
        )
        await self.user_repo.create(user)
        logger.info("user_registered", email=user.email, role=user.role, user_id=str(user.id))
        return UserResponse.model_validate(user)

    async def login(self, data: UserLoginRequest) -> TokenResponse:
        user = await self.user_repo.get_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            logger.warning("user_login_failed", email=data.email)
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("User account is inactive")

        claims = {"role": user.role, "email": user.email}
        access_token = create_jwt_token(subject=str(user.id), claims=claims, token_type="access")
        refresh_token = create_jwt_token(subject=str(user.id), claims=claims, token_type="refresh")

        logger.info("user_login_success", user_id=str(user.id), email=user.email)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_tokens(self, data: RefreshTokenRequest) -> TokenResponse:
        payload = decode_jwt_token(data.refresh_token, expected_type="refresh")
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise AuthenticationError("Invalid refresh token payload")

        user = await self.user_repo.get_by_id(uuid.UUID(user_id_str))
        if not user or not user.is_active:
            raise AuthenticationError("User account no longer active")

        claims = {"role": user.role, "email": user.email}
        new_access_token = create_jwt_token(subject=str(user.id), claims=claims, token_type="access")
        new_refresh_token = create_jwt_token(subject=str(user.id), claims=claims, token_type="refresh")

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def get_user_by_id(self, user_id: uuid.UUID) -> UserResponse:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        return UserResponse.model_validate(user)
