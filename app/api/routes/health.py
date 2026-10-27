"""Health check route."""

import sqlite3
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app import __version__
from app.api.deps import get_database
from app.schemas.energy import HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
def get_health(conn: sqlite3.Connection = Depends(get_database)) -> HealthResponse:
    """Check service health and database connectivity."""
    db_ok = False
    try:
        cursor = conn.execute("SELECT 1 AS check_col")
        row = cursor.fetchone()
        db_ok = bool(row and row["check_col"] == 1)
    except Exception:
        db_ok = False

    status_str = "healthy" if db_ok else "degraded"

    return HealthResponse(
        status=status_str,
        version=__version__,
        database_connected=db_ok,
        timestamp=datetime.now(UTC).isoformat(),
    )
