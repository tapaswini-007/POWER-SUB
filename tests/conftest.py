"""Pytest fixtures for POWER-SUB backend tests.

Provides isolated temporary databases, directories, and TestClient instances.
"""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.database.connection import init_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def test_environment() -> Generator[None, None, None]:
    """Isolate testing environment from production data/ directories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        db_path = str(temp_path / "test_power_sub.db")
        upload_dir = str(temp_path / "test_uploads")
        reports_dir = str(temp_path / "test_reports")

        # Point settings to temp directories
        old_db = settings.DATABASE_PATH
        old_upload = settings.UPLOAD_TEMP_DIR
        old_reports = settings.REPORTS_DIR
        old_api_key = settings.API_KEY

        settings.DATABASE_PATH = db_path
        settings.UPLOAD_TEMP_DIR = upload_dir
        settings.REPORTS_DIR = reports_dir
        settings.API_KEY = None  # default tests to no api key required

        settings.ensure_directories()
        init_db(db_path)

        yield

        # Restore original settings
        settings.DATABASE_PATH = old_db
        settings.UPLOAD_TEMP_DIR = old_upload
        settings.REPORTS_DIR = old_reports
        settings.API_KEY = old_api_key


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """TestClient fixture with app lifespan execution."""
    with TestClient(app) as test_client:
        yield test_client
