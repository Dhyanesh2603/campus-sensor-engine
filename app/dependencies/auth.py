import uuid
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_jwt_token
from app.dependencies.database import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository

http_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise AuthenticationError("Authorization header with Bearer token is required")

    payload = decode_jwt_token(credentials.credentials, expected_type="access")
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError("Token payload missing subject identifier")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise AuthenticationError("Invalid user ID in token")

    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise AuthenticationError("User associated with token no longer exists")

    if not user.is_active:
        raise AuthenticationError("User account is inactive")

    return user


async def require_organizer(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role.lower() != "organizer":
        raise PermissionDeniedError("Only organizers have permission to perform this action")
    return current_user
