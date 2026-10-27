"""File upload and preprocessing API endpoint."""

import os
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.deps import (
    STANDARD_LIMITATIONS,
    apply_rate_limit,
    get_database,
    require_api_key,
)
from app.core.config import settings
from app.database.models import DatasetRepository
from app.schemas.energy import UploadResponse
from app.services.data_extraction import extract_data_from_file
from app.services.preprocessing import preprocess_energy_data
from app.utils.file_validation import (
    detect_and_validate_file_type,
    stream_upload_to_temp_file,
)

router = APIRouter(
    prefix="/upload",
    tags=["Upload"],
    dependencies=[Depends(require_api_key), Depends(apply_rate_limit)],
)


@router.post(
    "",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload energy consumption file",
    description=(
        "Upload a CSV, XLSX, XLS, or PDF energy consumption document. "
        "The file is securely streamed, validated by signature, preprocessed, "
        "and persisted to the internal database. The original file is removed after parsing."
    ),
)
async def upload_energy_file(
    file: UploadFile = File(..., description="Energy consumption file (.csv, .xlsx, .xls, .pdf)"),
    sheet_name: str | None = Form(None, description="Sheet name for Excel workbooks"),
    date_format_hint: str | None = Form(
        None, description="Optional date format string (e.g. %Y-%m-%d)"
    ),
    energy_unit: str = Form("kWh", description="Unit of energy in file ('kWh', 'Wh', 'MWh')"),
    conn: sqlite3.Connection = Depends(get_database),
) -> UploadResponse:
    """Stream, validate, extract, clean, and store energy data."""
    temp_path: Path | None = None

    try:
        # 1. Stream file to dedicated temp directory with size limit check
        temp_path, display_name = await stream_upload_to_temp_file(file)

        # 2. Inspect signature / magic bytes and validate internal format
        file_type = detect_and_validate_file_type(temp_path, display_name)

        # 3. Extract raw tabular data
        raw_df, extract_warnings, available_sheets = extract_data_from_file(
            temp_path,
            file_type=file_type,
            sheet_name=sheet_name,
        )

        # 4. Clean and standardize records
        records, col_info, quality, prep_warnings = preprocess_energy_data(
            raw_df,
            sheet_name=sheet_name,
            date_format_hint=date_format_hint,
            energy_unit=energy_unit,
        )

        all_warnings = extract_warnings + prep_warnings
        if available_sheets and len(available_sheets) > 1:
            all_warnings.append(
                f"Multi-sheet Excel workbook detected. Extracted sheet: '{sheet_name or available_sheets[0]}'. "
                f"Available sheets: {', '.join(available_sheets)}."
            )

        # 5. Persist to database
        dataset_id = str(uuid.uuid4())
        expires_at = None
        if settings.DATASET_TTL_HOURS > 0:
            exp_dt = datetime.now(UTC) + timedelta(hours=settings.DATASET_TTL_HOURS)
            expires_at = exp_dt.isoformat()

        DatasetRepository.create_dataset(
            conn=conn,
            dataset_id=dataset_id,
            display_filename=display_name,
            file_type=file_type,
            record_count=len(records),
            quality=quality,
            column_info=col_info,
            expires_at=expires_at,
        )

        DatasetRepository.bulk_insert_records(conn, dataset_id, records)

        # 6. Build preview rows (first 10 accepted rows)
        preview_rows = records[:10]

        return UploadResponse(
            dataset_id=dataset_id,
            record_count=len(records),
            columns=col_info,
            data_quality=quality,
            warnings=all_warnings,
            preview_rows=preview_rows,
            limitations=STANDARD_LIMITATIONS,
        )

    finally:
        # Guarantee removal of uploaded temp file
        if temp_path and temp_path.exists():
            try:
                os.remove(temp_path)
            except OSError:
                pass
