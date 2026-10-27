"""Energy consumption analysis API routes."""

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    STANDARD_LIMITATIONS,
    get_database,
    require_api_key,
    validate_dataset_id,
)
from app.database.models import AnalysisRepository, DatasetRepository
from app.schemas.energy import EnergyAnalysisResponse
from app.services.energy_analysis import analyze_energy_dataset

router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"],
    dependencies=[Depends(require_api_key)],
)


@router.get(
    "/{dataset_id}",
    response_model=EnergyAnalysisResponse,
    summary="Analyze dataset consumption",
    description=(
        "Compute descriptive consumption statistics, cost summaries, baseline comparisons, "
        "and identify records with unusually high energy consumption via robust z-scores."
    ),
)
def get_energy_analysis(
    dataset_id: str = Depends(validate_dataset_id),
    baseline_method: Literal[
        "historical_mean",
        "historical_median",
        "rolling_average",
        "same_period_average",
        "user_target",
    ] = Query("historical_mean", description="Baseline comparison methodology"),
    target_kwh: float | None = Query(None, description="Target kWh for user_target baseline"),
    group_by: Literal["building", "department", "equipment"] | None = Query(
        None, description="Optional grouping dimension"
    ),
    granularity: Literal["daily", "weekly", "monthly"] | None = Query(
        None, description="Time aggregation granularity"
    ),
    conn: sqlite3.Connection = Depends(get_database),
) -> EnergyAnalysisResponse:
    """Analyze consumption, compare with baseline, and compute robust statistical deviations."""
    # 1. Fetch metadata and DataFrame
    dataset = DatasetRepository.get_dataset(conn, dataset_id)
    df = DatasetRepository.get_records_df(conn, dataset_id)

    # 2. Run analysis
    analysis = analyze_energy_dataset(
        df=df,
        baseline_method=baseline_method,
        target_kwh=target_kwh,
        group_by=group_by,
        granularity=granularity,
        quality_summary=dataset.get("quality", {}),
    )

    # 3. Cache result
    params = {
        "baseline_method": baseline_method,
        "target_kwh": target_kwh,
        "group_by": group_by,
        "granularity": granularity,
    }
    AnalysisRepository.save_analysis(conn, dataset_id, baseline_method, params, analysis)

    return EnergyAnalysisResponse(
        dataset_id=dataset_id,
        statistics=analysis["statistics"],
        cost_statistics=analysis["cost_statistics"],
        baseline_comparison=analysis["baseline_comparison"],
        breakdown_by_building=analysis["breakdown_by_building"],
        breakdown_by_department=analysis["breakdown_by_department"],
        breakdown_by_equipment=analysis["breakdown_by_equipment"],
        periodic_summary=analysis["periodic_summary"],
        high_consumption_records=analysis["high_consumption_records"],
        data_quality_summary=analysis["data_quality_summary"],
        limitations=STANDARD_LIMITATIONS,
    )
