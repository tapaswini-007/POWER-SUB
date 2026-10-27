"""Pydantic schemas for POWER-SUB backend."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    database_connected: bool
    timestamp: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "database_connected": True,
                "timestamp": "2026-10-21T08:00:00Z",
            }
        }
    )


class DataQualitySummary(BaseModel):
    """Data quality and cleaning metrics."""

    total_input_rows: int
    accepted_rows: int
    corrected_rows: int
    rejected_rows: int
    rejection_reasons: dict[str, int] = Field(default_factory=dict)
    correction_reasons: dict[str, int] = Field(default_factory=dict)
    example_rejections: list[dict[str, Any]] = Field(default_factory=list)
    granularity: str = "unknown"
    missing_values_per_column: dict[str, int] = Field(default_factory=dict)


class ColumnMappingInfo(BaseModel):
    """Detected and mapped columns."""

    detected: list[str]
    mapped: dict[str, str]
    unmapped: list[str]


class UploadResponse(BaseModel):
    """Response returned upon successful file upload and preprocessing."""

    dataset_id: str
    record_count: int
    columns: ColumnMappingInfo
    data_quality: DataQualitySummary
    warnings: list[str] = Field(default_factory=list)
    preview_rows: list[dict[str, Any]] = Field(default_factory=list)
    limitations: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "dataset_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                "record_count": 270,
                "columns": {
                    "detected": ["date", "building", "kwh", "cost"],
                    "mapped": {
                        "date": "date",
                        "building": "building",
                        "kwh": "energy_kwh",
                        "cost": "cost",
                    },
                    "unmapped": [],
                },
                "data_quality": {
                    "total_input_rows": 271,
                    "accepted_rows": 270,
                    "corrected_rows": 1,
                    "rejected_rows": 0,
                    "rejection_reasons": {},
                    "correction_reasons": {"duplicate_row_removed": 1},
                    "example_rejections": [],
                    "granularity": "daily",
                    "missing_values_per_column": {"operating_hours": 270},
                },
                "warnings": ["Converted Wh to kWh for energy column."],
                "preview_rows": [],
                "limitations": "Core Principle: A flagged anomaly is only a possible sign of energy waste...",
            }
        }
    )


class DatasetItem(BaseModel):
    """Summary of a stored dataset."""

    id: str
    display_filename: str
    file_type: str
    created_at: str
    expires_at: str | None = None
    record_count: int
    status: str


class DatasetListResponse(BaseModel):
    """Paginated list of datasets."""

    total: int
    limit: int
    offset: int
    items: list[DatasetItem]


class DatasetDetailResponse(DatasetItem):
    """Detailed information for a single dataset."""

    quality: DataQualitySummary | None = None
    column_info: ColumnMappingInfo | None = None


class HighConsumptionRecord(BaseModel):
    """Record flagged for unusually high consumption via robust statistics."""

    row_id: int
    date: str
    energy_kwh: float
    building: str | None = None
    department: str | None = None
    equipment: str | None = None
    deviation_score: float
    baseline_value: float
    deviation_pct: float | None = None


class ConsumptionStats(BaseModel):
    total_kwh: float
    mean_kwh: float
    median_kwh: float
    min_kwh: float
    max_kwh: float
    std_kwh: float


class CostStats(BaseModel):
    has_cost_data: bool
    total_cost: float | None = None
    average_cost_per_entry: float | None = None
    derived_cost_per_kwh: float | None = None
    note: str


class BaselineComparison(BaseModel):
    baseline_method_used: str
    baseline_kwh: float
    total_actual_kwh: float
    overall_deviation_pct: float | None = None
    baseline_status: str


class EnergyAnalysisResponse(BaseModel):
    """Complete energy analysis response."""

    dataset_id: str
    statistics: ConsumptionStats
    cost_statistics: CostStats
    baseline_comparison: BaselineComparison
    breakdown_by_building: dict[str, float] | None = None
    breakdown_by_department: dict[str, float] | None = None
    breakdown_by_equipment: dict[str, float] | None = None
    periodic_summary: dict[str, Any] = Field(default_factory=dict)
    high_consumption_records: list[HighConsumptionRecord] = Field(default_factory=list)
    data_quality_summary: DataQualitySummary
    limitations: str


class AnomalyDetectionRequest(BaseModel):
    """Parameters for AI-based anomaly detection."""

    contamination: float | None = Field(default=None, ge=0.001, le=0.5)
    sensitivity: Literal["low", "medium", "high"] | None = None
    n_estimators: int = Field(default=200, ge=50, le=1000)
    max_samples: Any = "auto"
    random_state: int | None = None
    features: list[str] | None = None
    use_rule_fallback: bool = True

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sensitivity": "medium",
                "n_estimators": 200,
                "use_rule_fallback": True,
            }
        }
    )


class ContributingFeature(BaseModel):
    feature: str
    actual_value: float
    dataset_median: float
    deviation: float
    direction: Literal["higher", "lower"]


class AnomalyRecord(BaseModel):
    row_id: int
    date: str
    energy_kwh: float
    building: str | None = None
    department: str | None = None
    equipment: str | None = None
    is_anomaly: bool
    anomaly_score: float
    severity: Literal["low", "medium", "high", "normal"]
    contributing_features: list[ContributingFeature] = Field(default_factory=list)


class ModelInfo(BaseModel):
    algorithm: str
    method: Literal["ai_isolation_forest", "rule_based_iqr"]
    parameters: dict[str, Any]
    features_used: list[str]
    features_dropped: dict[str, str] = Field(default_factory=dict)
    n_records: int
    random_seed: int
    trained_at: str


class AnomalySummary(BaseModel):
    total_records: int
    anomalies_flagged: int
    anomaly_percentage: float
    severity_counts: dict[str, int]


class AnomalyDetectionResponse(BaseModel):
    dataset_id: str
    status: Literal["completed", "insufficient_data"]
    message: str
    model_info: ModelInfo
    summary: AnomalySummary
    anomalies: list[AnomalyRecord]
    limitations: str


class SupportingMeasurement(BaseModel):
    metric: str
    value: float
    unit: str
    comparison_baseline: float | None = None


class RecommendationItem(BaseModel):
    id: str
    issue_detected: str
    supporting_measurements: list[SupportingMeasurement]
    suggested_action: str
    priority: Literal["low", "medium", "high"]
    estimated_savings: dict[str, Any] | None = None
    evidence_level: Literal["low", "medium", "high"]
    explanation: str
    required_additional_data: list[str] = Field(default_factory=list)
    limitations: str


class RecommendationsResponse(BaseModel):
    dataset_id: str
    total_recommendations: int
    recommendations: list[RecommendationItem]
    limitations: str
