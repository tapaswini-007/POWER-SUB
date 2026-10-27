"""Datasets management API routes: listing, detail lookup, and secure deletion."""

import os
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_database,
    require_api_key,
    validate_dataset_id,
)
from app.core.config import settings
from app.database.models import DatasetRepository
from app.schemas.energy import (
    DatasetDetailResponse,
    DatasetItem,
    DatasetListResponse,
)

router = APIRouter(
    prefix="/datasets",
    tags=["Datasets"],
    dependencies=[Depends(require_api_key)],
)


@router.get(
    "",
    response_model=DatasetListResponse,
    summary="List stored datasets",
    description="Retrieve a paginated list of all active datasets with metadata.",
)
def list_datasets(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Offset index for pagination"),
    conn: sqlite3.Connection = Depends(get_database),
) -> DatasetListResponse:
    """Fetch paginated dataset metadata summaries."""
    total = DatasetRepository.count_datasets(conn)
    datasets = DatasetRepository.list_datasets(conn, limit=limit, offset=offset)

    items = [
        DatasetItem(
            id=d["id"],
            display_filename=d["display_filename"],
            file_type=d["file_type"],
            created_at=d["created_at"],
            expires_at=d["expires_at"],
            record_count=d["record_count"],
            status=d["status"],
        )
        for d in datasets
    ]

    return DatasetListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


@router.get(
    "/{dataset_id}",
    response_model=DatasetDetailResponse,
    summary="Get dataset details",
    description="Retrieve detailed metadata and data quality metrics for a specific dataset ID.",
)
def get_dataset_detail(
    dataset_id: str = Depends(validate_dataset_id),
    conn: sqlite3.Connection = Depends(get_database),
) -> DatasetDetailResponse:
    """Fetch full quality summary and column mappings for a dataset."""
    d = DatasetRepository.get_dataset(conn, dataset_id)

    return DatasetDetailResponse(
        id=d["id"],
        display_filename=d["display_filename"],
        file_type=d["file_type"],
        created_at=d["created_at"],
        expires_at=d["expires_at"],
        record_count=d["record_count"],
        status=d["status"],
        quality=d["quality"] if d.get("quality") else None,
        column_info=d["column_info"] if d.get("column_info") else None,
    )


@router.delete(
    "/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete dataset",
    description=(
        "Permanently remove a dataset, its energy records, cached analysis results, "
        "and any associated generated report files."
    ),
)
def delete_dataset(
    dataset_id: str = Depends(validate_dataset_id),
    conn: sqlite3.Connection = Depends(get_database),
) -> None:
    """Delete dataset, cascading records, cached results, and generated files."""
    # Delete from database (energy_records, analysis_results, anomaly_results cascade via ON DELETE CASCADE)
    DatasetRepository.delete_dataset(conn, dataset_id)

    # Delete any generated report files associated with this dataset
    reports_dir = Path(settings.REPORTS_DIR).resolve()
    if reports_dir.exists():
        for report_file in reports_dir.glob(f"*{dataset_id[:8]}*"):
            try:
                os.remove(report_file)
            except OSError:
                pass
