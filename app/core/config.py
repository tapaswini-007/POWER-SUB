"""Configuration module for POWER-SUB backend.

Loads settings from environment variables with strong validation and safe defaults.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings backed by environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_ENV: Literal["development", "production"] = "development"
    DEBUG: bool = False

    DATABASE_PATH: str = "data/power_sub.db"
    UPLOAD_TEMP_DIR: str = "data/tmp"
    REPORTS_DIR: str = "generated_reports"

    MAX_UPLOAD_MB: int = Field(default=10, ge=1, le=100)
    MAX_ROWS: int = Field(default=200000, ge=1, le=1000000)
    MAX_COLUMNS: int = Field(default=100, ge=1, le=500)
    MAX_PDF_PAGES: int = Field(default=100, ge=1, le=1000)
    MAX_XLSX_UNCOMPRESSED_MB: int = Field(default=100, ge=1, le=1000)
    MAX_SHEETS: int = Field(default=10, ge=1, le=50)

    # Stored as comma-separated in env, parsed to list of origins
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost:8501"

    API_KEY: str | None = None
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, ge=1, le=10000)

    DATASET_TTL_HOURS: int = Field(default=168, ge=0)
    PERSIST_RESULTS: bool = True

    RANDOM_SEED: int = 42
    DEFAULT_CONTAMINATION: float = Field(default=0.05, gt=0.0, lt=0.5)
    MIN_RECORDS_FOR_ML: int = Field(default=30, ge=5)
    REQUEST_TIMEOUT_SECONDS: int = Field(default=60, ge=5, le=600)

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @property
    def allowed_origins_list(self) -> list[str]:
        """Return list of stripped allowed origins."""
        if not self.ALLOWED_ORIGINS:
            return []
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def validate_production_and_origins(self) -> "Settings":
        origins = self.allowed_origins_list

        if "*" in origins:
            raise ValueError(
                "Wildcard '*' is not permitted in ALLOWED_ORIGINS for security reasons."
            )

        if self.APP_ENV == "production":
            if not origins:
                raise ValueError("ALLOWED_ORIGINS cannot be empty when running in production mode.")

        return self

    def ensure_directories(self) -> None:
        """Create runtime directories if they do not exist."""
        db_path = Path(self.DATABASE_PATH).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        upload_dir = Path(self.UPLOAD_TEMP_DIR).resolve()
        upload_dir.mkdir(parents=True, exist_ok=True)

        reports_dir = Path(self.REPORTS_DIR).resolve()
        reports_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
