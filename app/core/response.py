from typing import Any, Generic, TypeVar
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    success: bool = True
    message: str = "Operation successful"
    data: DataT | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    message: str = "An error occurred"
    errors: list[str] = Field(default_factory=list)


def success_response(
    data: Any = None,
    message: str = "Operation successful",
    status_code: int = 200,
) -> JSONResponse:
    content = {
        "success": True,
        "message": message,
        "data": data,
    }
    return JSONResponse(status_code=status_code, content=content)


def error_response(
    message: str = "An error occurred",
    errors: list[str] | None = None,
    status_code: int = 400,
) -> JSONResponse:
    content = {
        "success": False,
        "message": message,
        "errors": errors or [],
    }
    return JSONResponse(status_code=status_code, content=content)
