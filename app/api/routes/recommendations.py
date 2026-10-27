"""Intelligent energy recommendations API routes."""

import sqlite3

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    STANDARD_LIMITATIONS,
    get_database,
    require_api_key,
    validate_dataset_id,
)
from app.database.models import DatasetRepository
from app.schemas.energy import RecommendationItem, RecommendationsResponse
from app.services.recommendations import generate_recommendations

router = APIRouter(
    prefix="/recommendations",
    tags=["Recommendations"],
    dependencies=[Depends(require_api_key)],
)


@router.get(
    "/{dataset_id}",
    response_model=RecommendationsResponse,
    summary="Get intelligent energy efficiency recommendations",
    description=(
        "Generate grounded, evidence-driven recommendations based on actual dataset observations. "
        "Evaluates off-hours base draw, persistent elevations above baseline, high-consuming entities, "
        "and data logging gaps. Financial savings are computed only when supported by dataset cost records "
        "or an explicit user-provided tariff."
    ),
)
def get_recommendations(
    dataset_id: str = Depends(validate_dataset_id),
    tariff_per_kwh: float | None = Query(
        None,
        gt=0.0,
        description="Optional electricity tariff in $/kWh for estimated savings calculations",
    ),
    conn: sqlite3.Connection = Depends(get_database),
) -> RecommendationsResponse:
    """Evaluate energy records and synthesize grounded efficiency actions."""
    dataset = DatasetRepository.get_dataset(conn, dataset_id)
    df = DatasetRepository.get_records_df(conn, dataset_id)

    raw_recs = generate_recommendations(
        df=df,
        tariff_per_kwh=tariff_per_kwh,
        quality_summary=dataset.get("quality", {}),
    )

    items = [RecommendationItem(**r) for r in raw_recs]

    return RecommendationsResponse(
        dataset_id=dataset_id,
        total_recommendations=len(items),
        recommendations=items,
        limitations=STANDARD_LIMITATIONS,
    )
