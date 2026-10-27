"""Report generation and export API routes for CSV and publication-ready PDF formats."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import (
    apply_rate_limit,
    get_database,
    require_api_key,
    validate_dataset_id,
)
from app.core.config import settings
from app.database.models import AnalysisRepository, DatasetRepository
from app.services.anomaly_detection import detect_anomalies
from app.services.energy_analysis import analyze_energy_dataset
from app.services.recommendations import generate_recommendations
from app.services.report_generation import generate_csv_report, generate_pdf_report

router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
    dependencies=[Depends(require_api_key), Depends(apply_rate_limit)],
)


def prepare_report_context(
    conn: sqlite3.Connection,
    dataset_id: str,
    tariff_per_kwh: float | None = None,
) -> tuple:
    """Fetch dataset, analysis, anomalies, and recommendations needed for report generation."""
    dataset = DatasetRepository.get_dataset(conn, dataset_id)
    df = DatasetRepository.get_records_df(conn, dataset_id)

    # 1. Analysis
    analysis = analyze_energy_dataset(
        df=df,
        baseline_method="historical_mean",
        quality_summary=dataset.get("quality", {}),
    )

    # 2. Anomalies: fetch latest or execute default
    latest_anom = AnalysisRepository.get_latest_anomaly_result(conn, dataset_id)
    if latest_anom:
        anomalies_data = latest_anom["result"]
    else:
        anomalies_data = detect_anomalies(
            df=df,
            sensitivity="medium",
            use_rule_fallback=True,
        )

    # 3. Recommendations
    recs = generate_recommendations(
        df=df,
        tariff_per_kwh=tariff_per_kwh,
        quality_summary=dataset.get("quality", {}),
    )

    return dataset, df, analysis, anomalies_data, recs


@router.get(
    "/{dataset_id}/csv",
    summary="Download CSV energy report",
    description="Export a formula-injection neutralized CSV report with anomaly classifications and UTF-8 BOM.",
)
def download_csv_report(
    dataset_id: str = Depends(validate_dataset_id),
    tariff_per_kwh: float | None = Query(None, gt=0.0),
    conn: sqlite3.Connection = Depends(get_database),
) -> Response:
    """Stream sanitized CSV report."""
    dataset, df, analysis, anomalies_data, recs = prepare_report_context(
        conn, dataset_id, tariff_per_kwh
    )

    csv_bytes = generate_csv_report(
        dataset=dataset,
        df=df,
        analysis=analysis,
        anomalies=anomalies_data,
        recommendations=recs,
    )

    date_str = datetime.now(UTC).strftime("%Y%m%d")
    filename = f"power_sub_report_{dataset_id[:8]}_{date_str}.csv"

    # Persist report file to REPORTS_DIR
    reports_dir = Path(settings.REPORTS_DIR).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file_path = reports_dir / filename
    report_file_path.write_bytes(csv_bytes)

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "text/csv; charset=utf-8",
    }
    return Response(content=csv_bytes, media_type="text/csv; charset=utf-8", headers=headers)


@router.get(
    "/{dataset_id}/pdf",
    summary="Download publication-grade PDF report",
    description="Export a publication-ready PDF containing executive summaries, non-GUI Matplotlib charts, and recommendations.",
)
def download_pdf_report(
    dataset_id: str = Depends(validate_dataset_id),
    tariff_per_kwh: float | None = Query(None, gt=0.0),
    conn: sqlite3.Connection = Depends(get_database),
) -> Response:
    """Stream formatted PDF report."""
    dataset, df, analysis, anomalies_data, recs = prepare_report_context(
        conn, dataset_id, tariff_per_kwh
    )

    pdf_bytes = generate_pdf_report(
        dataset=dataset,
        df=df,
        analysis=analysis,
        anomalies=anomalies_data,
        recommendations=recs,
    )

    date_str = datetime.now(UTC).strftime("%Y%m%d")
    filename = f"power_sub_report_{dataset_id[:8]}_{date_str}.pdf"

    # Persist report file to REPORTS_DIR
    reports_dir = Path(settings.REPORTS_DIR).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file_path = reports_dir / filename
    report_file_path.write_bytes(pdf_bytes)

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "application/pdf",
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
