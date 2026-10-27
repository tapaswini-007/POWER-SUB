"""AI-based anomaly detection API routes: triggering model and retrieving cached results."""

import sqlite3

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    STANDARD_LIMITATIONS,
    get_database,
    require_api_key,
    validate_dataset_id,
)
from app.core.config import settings
from app.core.errors import NotFoundError
from app.database.models import AnalysisRepository, DatasetRepository
from app.schemas.energy import (
    AnomalyDetectionRequest,
    AnomalyDetectionResponse,
    AnomalyRecord,
    AnomalySummary,
    ModelInfo,
)
from app.services.anomaly_detection import detect_anomalies, generate_params_hash

router = APIRouter(
    prefix="/anomalies",
    tags=["Anomalies"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "/{dataset_id}",
    response_model=AnomalyDetectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Run AI anomaly detection",
    description=(
        "Train an IsolationForest model on dataset features to flag unusual consumption patterns. "
        "Includes cyclical time features, guards against division-by-zero, and automatically falls back "
        "to a robust IQR rule-based detector if records are below the minimum threshold. "
        "Identical parameter configurations are cached deterministically."
    ),
)
def run_anomaly_detection(
    params_body: AnomalyDetectionRequest,
    dataset_id: str = Depends(validate_dataset_id),
    conn: sqlite3.Connection = Depends(get_database),
) -> AnomalyDetectionResponse:
    """Execute AI anomaly detection or return deterministic cached result."""
    # Ensure dataset exists
    DatasetRepository.get_dataset(conn, dataset_id)

    # 1. Check cache for identical parameters
    params_dict = params_body.model_dump()
    params_hash = generate_params_hash(params_dict)

    if settings.PERSIST_RESULTS:
        cached = AnalysisRepository.get_cached_anomaly_result(conn, dataset_id, params_hash)
        if cached:
            res_data = cached["result"]
            return AnomalyDetectionResponse(
                dataset_id=dataset_id,
                status=res_data["status"],
                message=f"[Cached Result] {res_data['message']}",
                model_info=ModelInfo(**cached["model_info"]),
                summary=AnomalySummary(**res_data["summary"]),
                anomalies=[AnomalyRecord(**a) for a in res_data["anomalies"]],
                limitations=STANDARD_LIMITATIONS,
            )

    # 2. Load dataset records
    df = DatasetRepository.get_records_df(conn, dataset_id)

    # 3. Train model and detect anomalies
    detection_result = detect_anomalies(
        df=df,
        contamination=params_body.contamination,
        sensitivity=params_body.sensitivity,
        n_estimators=params_body.n_estimators,
        max_samples=params_body.max_samples,
        random_state=params_body.random_state,
        features=params_body.features,
        use_rule_fallback=params_body.use_rule_fallback,
    )

    # 4. Save to anomaly_results table
    if settings.PERSIST_RESULTS:
        AnalysisRepository.save_anomaly_result(
            conn=conn,
            dataset_id=dataset_id,
            params=params_dict,
            params_hash=params_hash,
            model_info=detection_result["model_info"],
            result=detection_result,
        )

    return AnomalyDetectionResponse(
        dataset_id=dataset_id,
        status=detection_result["status"],
        message=detection_result["message"],
        model_info=ModelInfo(**detection_result["model_info"]),
        summary=AnomalySummary(**detection_result["summary"]),
        anomalies=[AnomalyRecord(**a) for a in detection_result["anomalies"]],
        limitations=STANDARD_LIMITATIONS,
    )


@router.get(
    "/{dataset_id}",
    response_model=AnomalyDetectionResponse,
    summary="Get latest anomaly detection results",
    description="Retrieve the most recent stored anomaly detection results for a dataset with pagination and filtering.",
)
def get_latest_anomalies(
    dataset_id: str = Depends(validate_dataset_id),
    only_anomalies: bool = Query(
        False, description="Filter output to only flagged anomalous records"
    ),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    offset: int = Query(0, ge=0, description="Offset index for pagination"),
    conn: sqlite3.Connection = Depends(get_database),
) -> AnomalyDetectionResponse:
    """Retrieve most recent anomaly detection run."""
    DatasetRepository.get_dataset(conn, dataset_id)

    latest = AnalysisRepository.get_latest_anomaly_result(conn, dataset_id)
    if not latest:
        raise NotFoundError(
            f"No anomaly detection results found for dataset '{dataset_id}'. "
            f"Please run POST /api/v1/anomalies/{dataset_id} first."
        )

    result_data = latest["result"]
    anomalies_list = result_data.get("anomalies", [])

    if only_anomalies:
        anomalies_list = [a for a in anomalies_list if a.get("is_anomaly")]

    paginated_anomalies = anomalies_list[offset : offset + limit]

    return AnomalyDetectionResponse(
        dataset_id=dataset_id,
        status=result_data["status"],
        message=result_data["message"],
        model_info=ModelInfo(**latest["model_info"]),
        summary=AnomalySummary(**result_data["summary"]),
        anomalies=[AnomalyRecord(**a) for a in paginated_anomalies],
        limitations=STANDARD_LIMITATIONS,
    )
