"""Main FastAPI application entry point for POWER-SUB backend."""

import contextlib
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.routes import (
    analysis,
    anomalies,
    datasets,
    health,
    recommendations,
    reports,
    upload,
)
from app.core.config import settings
from app.core.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import logger, setup_logging
from app.core.security import SecurityHeadersMiddleware
from app.database.connection import get_db, init_db
from app.database.models import DatasetRepository


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle handler."""
    # Ensure all directories exist
    settings.ensure_directories()
    setup_logging(settings.LOG_LEVEL)

    # Initialize database
    init_db()

    # Perform TTL cleanup of expired datasets at startup
    if settings.DATASET_TTL_HOURS > 0:
        try:
            with get_db() as conn:
                removed = DatasetRepository.delete_expired_datasets(conn)
                if removed > 0:
                    logger.info(f"TTL cleanup removed {removed} expired dataset(s) at startup.")
        except Exception as e:
            logger.warning(f"Error running TTL cleanup at startup: {e}")

    logger.info(f"POWER-SUB Backend v{__version__} started ({settings.APP_ENV} mode).")
    yield
    logger.info("POWER-SUB Backend shutting down.")


# Determine docs availability based on environment
docs_url = "/docs" if settings.APP_ENV != "production" or settings.DEBUG else None
redoc_url = "/redoc" if settings.APP_ENV != "production" or settings.DEBUG else None

app = FastAPI(
    title="POWER-SUB: Energy Waste Detection & Intelligent Recommendations API",
    description=(
        "Research backend API for energy consumption analysis, statistical and "
        "AI-based anomaly detection, and evidence-driven energy efficiency recommendations."
    ),
    version=__version__,
    docs_url=docs_url,
    redoc_url=redoc_url,
    lifespan=lifespan,
)

# 1. Custom Security Headers & Request-ID Middleware
app.add_middleware(SecurityHeadersMiddleware)

# 2. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "X-Request-ID", "Accept"],
    max_age=600,
)

# 3. Exception Handlers
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


# 4. Root Endpoint
@app.get("/", tags=["Root"])
def root_pointer():
    """Root endpoint pointing to interactive documentation and health."""
    return {
        "service": "POWER-SUB Backend",
        "version": __version__,
        "documentation": "/docs" if docs_url else "Disabled in production",
        "health": "/api/v1/health",
    }


# 5. Register Routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(datasets.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(anomalies.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
