"""SQLite database connection management and lifecycle."""

import contextlib
import os
import sqlite3
from collections.abc import Generator
from pathlib import Path

from app.core.config import settings
from app.core.logging import logger

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    display_filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    record_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ready',
    quality_json TEXT,
    column_info_json TEXT
);

CREATE TABLE IF NOT EXISTS energy_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    row_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    energy_kwh REAL NOT NULL,
    building TEXT,
    department TEXT,
    equipment TEXT,
    cost REAL,
    temperature REAL,
    operating_hours REAL,
    was_corrected INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_records_dataset_id ON energy_records(dataset_id);
CREATE INDEX IF NOT EXISTS idx_records_dataset_date ON energy_records(dataset_id, date);

CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    baseline_method TEXT NOT NULL,
    params_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS anomaly_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    params_json TEXT NOT NULL,
    params_hash TEXT NOT NULL,
    model_info_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_anomaly_cache ON anomaly_results(dataset_id, params_hash);
"""


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Create and configure a single SQLite connection."""
    target_path = db_path or settings.DATABASE_PATH
    Path(target_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        target_path,
        timeout=10.0,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


@contextlib.contextmanager
def get_db(db_path: str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connections per request or task."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str | None = None) -> None:
    """Initialize database tables and indexes."""
    target_path = db_path or settings.DATABASE_PATH
    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
    with get_db(target_path) as conn:
        conn.executescript(SCHEMA_SQL)
    logger.info(f"Database initialized successfully at {target_path}")


def reset_database(confirmed: bool = False, db_path: str | None = None) -> bool:
    """Safely reset the database by deleting and recreating it."""
    if not confirmed:
        raise ValueError("Database reset requires explicit confirmation (confirmed=True).")

    target_path = Path(db_path or settings.DATABASE_PATH).resolve()

    # Also remove WAL and SHM files if present
    for suffix in ["", "-wal", "-shm"]:
        p = Path(str(target_path) + suffix)
        if p.exists():
            try:
                os.remove(p)
            except OSError as e:
                logger.warning(f"Could not remove DB file {p}: {e}")

    init_db(str(target_path))
    logger.info("Database reset complete.")
    return True
