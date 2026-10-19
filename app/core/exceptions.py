from typing import Any


class AppException(Exception):
    def __init__(
        self,
        message: str = "An unexpected error occurred",
        status_code: int = 500,
        errors: list[str] | None = None,
        data: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors or []
        self.data = data


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message=message, status_code=404)


class AuthenticationError(AppException):
    def __init__(self, message: str = "Could not validate credentials") -> None:
        super().__init__(message=message, status_code=401)


class PermissionDeniedError(AppException):
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message=message, status_code=403)


class ConflictError(AppException):
    def __init__(self, message: str = "Resource conflict") -> None:
        super().__init__(message=message, status_code=409)


class ValidationError(AppException):
    def __init__(self, message: str = "Validation error", errors: list[str] | None = None) -> None:
        super().__init__(message=message, status_code=422, errors=errors or [])


class DatabaseError(AppException):
    def __init__(self, message: str = "A database error occurred") -> None:
        super().__init__(message=message, status_code=500)


class RateLimitError(AppException):
    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(message=message, status_code=429)
