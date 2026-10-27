"""Custom exception classes and global error response envelopes."""

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import logger


class AppError(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: list[Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND"):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ValidationError(AppError):
    def __init__(self, message: str, details: list[Any] | None = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class BadRequestError(AppError):
    def __init__(self, message: str, code: str = "BAD_REQUEST", details: list[Any] | None = None):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class AuthenticationError(AppError):
    def __init__(self, message: str = "Invalid or missing API key"):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class PayloadTooLargeError(AppError):
    def __init__(self, message: str = "Uploaded file exceeds maximum allowed size"):
        super().__init__(
            message=message,
            code="PAYLOAD_TOO_LARGE",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )


class UnsupportedMediaTypeError(AppError):
    def __init__(self, message: str = "Unsupported media type"):
        super().__init__(
            message=message,
            code="UNSUPPORTED_MEDIA_TYPE",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )


class RateLimitExceededError(AppError):
    def __init__(self, message: str = "Rate limit exceeded. Please try again later."):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


def make_error_envelope(
    code: str, message: str, request_id: str, details: list[Any] | None = None
) -> dict:
    """Produce standardized error envelope."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        },
        "request_id": request_id,
    }


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    logger.warning(
        f"Handled application error [{exc.code}]: {exc.message}",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": exc.status_code,
        },
    )
    content = make_error_envelope(exc.code, exc.message, request_id, exc.details)
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers={"X-Request-ID": request_id},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    code = "HTTP_ERROR"
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        code = "NOT_FOUND"
    elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
        code = "UNAUTHORIZED"
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        code = "FORBIDDEN"
    elif exc.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        code = "METHOD_NOT_ALLOWED"

    logger.warning(
        f"HTTP exception [{exc.status_code}]: {exc.detail}",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": exc.status_code,
        },
    )
    content = make_error_envelope(code, str(exc.detail), request_id)
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers={"X-Request-ID": request_id},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    sanitized_errors = []
    for err in exc.errors():
        sanitized_errors.append(
            {
                "loc": [str(loc) for loc in err.get("loc", [])],
                "msg": err.get("msg", "Invalid value"),
                "type": err.get("type", "value_error"),
            }
        )

    logger.warning(
        "Request validation error",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
        },
    )
    content = make_error_envelope(
        "VALIDATION_ERROR",
        "Request parameters or body failed schema validation.",
        request_id,
        sanitized_errors,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=content,
        headers={"X-Request-ID": request_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    # Log full traceback server-side only with request_id
    logger.exception(
        f"Unhandled server error: {exc}",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        },
    )
    # Never leak internal traceback, file paths, or exception details to the client
    content = make_error_envelope(
        "INTERNAL_SERVER_ERROR",
        "An internal server error occurred. Please contact system administrator with the request ID.",
        request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content,
        headers={"X-Request-ID": request_id},
    )
