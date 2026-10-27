"""Security middleware, authentication, rate limiting, and security headers."""

import secrets
import time
import uuid
from collections import defaultdict
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.errors import AuthenticationError, RateLimitExceededError
from app.core.logging import logger


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforce strict HTTP security headers and assign request IDs."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id

        client_host = request.client.host if request.client else "unknown"

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Attach standard security headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"

        # Prevent browser caching of dynamic data API responses
        if request.url.path.startswith("/api/v1/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"

        logger.info(
            f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": client_host,
            },
        )

        return response


class InMemoryRateLimiter:
    """Sliding-window in-memory rate limiter per client IP."""

    def __init__(self, requests_per_minute: int = 60):
        self.limit = requests_per_minute
        self.window = 60.0  # seconds
        self._history: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> bool:
        """Return True if allowed, False if exceeded."""
        now = time.time()
        timestamps = self._history[key]

        # Evict timestamps outside the window
        valid_from = now - self.window
        self._history[key] = [t for t in timestamps if t > valid_from]

        if len(self._history[key]) >= self.limit:
            return False

        self._history[key].append(now)
        return True

    def reset(self) -> None:
        """Clear all rate limit history."""
        self._history.clear()


rate_limiter = InMemoryRateLimiter(settings.RATE_LIMIT_PER_MINUTE)


def verify_api_key(request: Request) -> None:
    """Verify X-API-Key header if API_KEY setting is configured."""
    if not settings.API_KEY:
        return

    # Check header
    provided_key = request.headers.get("X-API-Key")
    if not provided_key:
        raise AuthenticationError("Missing X-API-Key header")

    if not secrets.compare_digest(provided_key, settings.API_KEY):
        raise AuthenticationError("Invalid X-API-Key")


def check_rate_limit(request: Request) -> None:
    """Check IP against the in-memory rate limiter."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not rate_limiter.check(client_ip):
        raise RateLimitExceededError(
            "Rate limit exceeded for your IP address. Please wait a moment."
        )
