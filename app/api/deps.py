"""API dependency injection: database, auth, rate-limiting, and validation."""

import re
import sqlite3
from collections.abc import Generator

from fastapi import Request

from app.core.errors import NotFoundError
from app.core.security import check_rate_limit, verify_api_key
from app.database.connection import get_db

UUID4_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

STANDARD_LIMITATIONS: str = (
    "Core Principle: A flagged anomaly is only a possible sign of energy waste, "
    "not proof. Statistical deviations may be caused by legitimate operational events "
    "(such as high production shifts, weather extremes, scheduled maintenance, or "
    "sensor calibration). Recommendations provide indicative guidance and require "
    "on-site technical validation before implementing changes."
)


def get_database() -> Generator[sqlite3.Connection, None, None]:
    """Dependency that yields an active SQLite connection and commits/rolls back."""
    with get_db() as conn:
        yield conn


def require_api_key(request: Request) -> None:
    """Dependency to enforce API key if configured."""
    verify_api_key(request)


def apply_rate_limit(request: Request) -> None:
    """Dependency to enforce client IP rate limit."""
    check_rate_limit(request)


def validate_dataset_id(dataset_id: str) -> str:
    """Validate that dataset_id is a valid UUID4, otherwise raise 404 without leaking internals."""
    if not dataset_id or not UUID4_REGEX.match(dataset_id):
        raise NotFoundError(f"Dataset with ID '{dataset_id}' not found.")
    return dataset_id
