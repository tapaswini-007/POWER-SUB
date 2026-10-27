# POWER-SUB API Contract & Integration Specifications

This document defines the verified REST API contract between the **POWER-SUB Frontend** dashboard and the **FastAPI Backend**, derived directly from the live OpenAPI schema (`openapi_spec.json`) and backend service routes.

---

## 1. General Principles & Security Headers

### Base URL
- Default local URL: `http://127.0.0.1:8000` (or `http://localhost:8000`)
- CORS requirement: Frontend origin (e.g. `http://127.0.0.1:5173` or `http://localhost:5173`) must be included in backend `ALLOWED_ORIGINS`.

### Authentication
- Optional `X-API-Key` header compared with constant-time equality.
- When `API_KEY` is configured in backend environment, all endpoints under `/api/v1/*` except `/health` require `X-API-Key`.
- Handled exclusively in memory by frontend (never stored in `localStorage` or `sessionStorage`).

### Response Headers
- `X-Request-ID`: Unique transaction ID (`uuid4().hex`) generated for tracing.
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` (data endpoints)

### Standard Error Envelope
All `4xx` and `5xx` error responses strictly follow this JSON envelope:
```json
{
  "error": {
    "code": "NOT_FOUND | VALIDATION_ERROR | BAD_REQUEST | UNAUTHORIZED | PAYLOAD_TOO_LARGE | UNSUPPORTED_MEDIA_TYPE | RATE_LIMIT_EXCEEDED | INTERNAL_SERVER_ERROR",
    "message": "User-safe error explanation.",
    "details": []
  },
  "request_id": "4e6ae32e1fdd4d528ccf31ed2fdb0f74"
}
```

---

## 2. Endpoints Specification

### 2.1 Health Check
- **Path**: `GET /api/v1/health`
- **Auth**: Exempt
- **Response `200 OK`**:
```json
{
  "status": "healthy" | "degraded",
  "version": "1.0.0",
  "database_connected": true,
  "timestamp": "2026-10-21T08:00:00Z"
}
```

---

### 2.2 File Upload & Preprocessing
- **Path**: `POST /api/v1/upload`
- **Content-Type**: `multipart/form-data`
- **Form Parameters**:
  - `file`: (Binary File, required) Allowed extensions: `.csv`, `.xlsx`, `.xls`, `.pdf`. Max size: 10 MB.
  - `sheet_name`: (string, optional) Target sheet for Excel workbooks.
  - `date_format_hint`: (string, optional) E.g. `%Y-%m-%d`.
  - `energy_unit`: (string, optional, default `"kWh"`) Allowed: `"kWh"`, `"Wh"`, `"MWh"`.
- **Response `201 Created`**:
```json
{
  "dataset_id": "uuid4-string",
  "record_count": 270,
  "columns": {
    "detected": ["date", "building", "kwh", "cost"],
    "mapped": {"date": "date", "kwh": "energy_kwh", "building": "building", "cost": "cost"},
    "unmapped": []
  },
  "data_quality": {
    "total_input_rows": 271,
    "accepted_rows": 270,
    "corrected_rows": 1,
    "rejected_rows": 0,
    "rejection_reasons": {},
    "correction_reasons": {"exact_duplicate_rows_dropped": 1},
    "example_rejections": [],
    "granularity": "daily",
    "missing_values_per_column": {"cost": 1, "temperature": 0}
  },
  "warnings": ["Converted Wh to kWh..."],
  "preview_rows": [
    {
      "row_id": 1,
      "date": "2024-01-01T00:00:00",
      "energy_kwh": 120.5,
      "building": "Building_A",
      "department": "Operations",
      "equipment": "HVAC_Main",
      "cost": 18.08,
      "temperature": 15.2,
      "operating_hours": 8.0,
      "was_corrected": false
    }
  ],
  "limitations": "Core Principle: A flagged anomaly is only a possible sign of energy waste..."
}
```

---

### 2.3 Datasets Management

#### List Datasets
- **Path**: `GET /api/v1/datasets`
- **Query Parameters**:
  - `limit`: int (1-100, default 50)
  - `offset`: int (>= 0, default 0)
- **Response `200 OK`**:
```json
{
  "total": 5,
  "limit": 50,
  "offset": 0,
  "items": [
    {
      "id": "uuid4-string",
      "display_filename": "sample_energy.csv",
      "file_type": "csv",
      "created_at": "2026-10-21T08:00:00Z",
      "expires_at": null,
      "record_count": 270,
      "status": "ready"
    }
  ]
}
```

#### Get Dataset Details
- **Path**: `GET /api/v1/datasets/{dataset_id}`
- **Response `200 OK`**: `DatasetDetailResponse`
  - Includes all dataset item fields plus `quality` (`DataQualitySummary`) and `column_info` (`ColumnMappingInfo`).

#### Delete Dataset
- **Path**: `DELETE /api/v1/datasets/{dataset_id}`
- **Response `204 No Content`**
  - Cascades deletion of all records, cached analysis, anomaly models, and generated report files.

---

### 2.4 Energy Consumption Analysis
- **Path**: `GET /api/v1/analysis/{dataset_id}`
- **Query Parameters**:
  - `baseline_method`: `"historical_mean"` | `"historical_median"` | `"rolling_average"` | `"same_period_average"` | `"user_target"`
  - `target_kwh`: float > 0 (required if `user_target`)
  - `group_by`: `"building"` | `"department"` | `"equipment"` (optional)
  - `granularity`: `"daily"` | `"weekly"` | `"monthly"` (optional)
- **Response `200 OK`**:
```json
{
  "dataset_id": "uuid4-string",
  "statistics": {
    "total_kwh": 32540.5,
    "mean_kwh": 120.52,
    "median_kwh": 118.4,
    "min_kwh": 45.2,
    "max_kwh": 450.0,
    "std_kwh": 28.6
  },
  "cost_statistics": {
    "has_cost_data": true,
    "total_cost": 4881.08,
    "average_cost_per_entry": 18.08,
    "derived_cost_per_kwh": 0.15,
    "note": "Derived exclusively from reported cost and consumption in this dataset."
  },
  "baseline_comparison": {
    "baseline_method_used": "historical_mean",
    "baseline_kwh": 120.52,
    "total_actual_kwh": 32540.5,
    "overall_deviation_pct": 0.0,
    "baseline_status": "Baseline successfully calculated."
  },
  "breakdown_by_building": {"Building_A": 18200.0, "Building_B": 14340.5},
  "breakdown_by_department": {"Operations": 32540.5},
  "breakdown_by_equipment": {"HVAC_Main": 32540.5},
  "periodic_summary": {
    "monthly": [
      {"period": "2024-01", "total_kwh": 10500.0, "mean_kwh": 116.6, "records": 90}
    ]
  },
  "high_consumption_records": [
    {
      "row_id": 15,
      "date": "2024-01-15",
      "energy_kwh": 450.0,
      "building": "Building_A",
      "department": "Operations",
      "equipment": "HVAC_Main",
      "deviation_score": 5.4,
      "baseline_value": 118.4,
      "deviation_pct": 280.07
    }
  ],
  "data_quality_summary": { ... },
  "limitations": "Core Principle: A flagged anomaly is only a possible sign of energy waste..."
}
```

---

### 2.5 AI Anomaly Detection

#### Run Anomaly Detection
- **Path**: `POST /api/v1/anomalies/{dataset_id}`
- **Body JSON**:
```json
{
  "sensitivity": "medium",
  "contamination": null,
  "n_estimators": 200,
  "max_samples": "auto",
  "random_state": 42,
  "features": null,
  "use_rule_fallback": true
}
```
- **Response `200 OK`**:
```json
{
  "dataset_id": "uuid4-string",
  "status": "completed" | "insufficient_data",
  "message": "Successfully executed IsolationForest anomaly detection on 270 records.",
  "model_info": {
    "algorithm": "scikit-learn IsolationForest",
    "method": "ai_isolation_forest" | "rule_based_iqr",
    "parameters": {"contamination": 0.05, "n_estimators": 200, "random_state": 42},
    "features_used": ["energy_kwh", "operating_hours", "dow_sin", "dow_cos"],
    "features_dropped": {},
    "n_records": 270,
    "random_seed": 42,
    "trained_at": "2026-10-21T08:00:00Z"
  },
  "summary": {
    "total_records": 270,
    "anomalies_flagged": 14,
    "anomaly_percentage": 5.19,
    "severity_counts": {"high": 4, "medium": 7, "low": 3, "normal": 256}
  },
  "anomalies": [
    {
      "row_id": 15,
      "date": "2024-01-15",
      "energy_kwh": 450.0,
      "building": "Building_A",
      "department": "Operations",
      "equipment": "HVAC_Main",
      "is_anomaly": true,
      "anomaly_score": 0.285,
      "severity": "high",
      "contributing_features": [
        {
          "feature": "energy_kwh",
          "actual_value": 450.0,
          "dataset_median": 118.4,
          "deviation": 5.4,
          "direction": "higher"
        }
      ]
    }
  ],
  "limitations": "Core Principle: A flagged anomaly is only a possible sign of energy waste..."
}
```

#### Get Latest Anomalies
- **Path**: `GET /api/v1/anomalies/{dataset_id}`
- **Query Parameters**:
  - `only_anomalies`: bool (default `false`)
  - `limit`: int (1-500, default 100)
  - `offset`: int (>= 0, default 0)
- **Response `200 OK`**: Same schema as POST.
- **Response `404 Not Found`**: Returned if no model run has been performed for this dataset yet.

---

### 2.6 Intelligent Recommendations
- **Path**: `GET /api/v1/recommendations/{dataset_id}`
- **Query Parameters**:
  - `tariff_per_kwh`: float > 0 (optional)
- **Response `200 OK`**:
```json
{
  "dataset_id": "uuid4-string",
  "total_recommendations": 2,
  "recommendations": [
    {
      "id": "REC-OFFHOURS-001",
      "issue_detected": "Significant energy consumption detected during zero-operating-hour periods",
      "supporting_measurements": [
        {"metric": "zero_operating_hours_days", "value": 12.0, "unit": "days", "comparison_baseline": 0.0},
        {"metric": "total_off_hours_consumption", "value": 1420.5, "unit": "kWh", "comparison_baseline": 0.0}
      ],
      "suggested_action": "Implement automated building management system (BMS) setback schedules...",
      "priority": "high",
      "estimated_savings": {
        "potential_kwh_reduction": 994.35,
        "potential_cost_savings": 149.15,
        "unit": "USD",
        "cost_source": "dataset_reported_cost",
        "confidence_label": "potential, not guaranteed",
        "note": "Calculated as 994.4 excess kWh multiplied by dataset_reported_cost ($0.1500/kWh). Requires field validation."
      },
      "evidence_level": "high",
      "explanation": "Detected 12 days where equipment or facility was recorded with 0 operating hours...",
      "required_additional_data": ["Submeter telemetry for lighting vs HVAC baseload"],
      "limitations": "Core Principle: A flagged anomaly is only a possible sign of energy waste..."
    }
  ],
  "limitations": "Core Principle: A flagged anomaly is only a possible sign of energy waste..."
}
```

---

### 2.7 Reports Export

#### CSV Report Download
- **Path**: `GET /api/v1/reports/{dataset_id}/csv`
- **Response `200 OK`**:
  - `Content-Type`: `text/csv; charset=utf-8`
  - `Content-Disposition`: `attachment; filename="power_sub_report_<id8>_<YYYYMMDD>.csv"`
  - Encoded with UTF-8 BOM (`\xef\xbb\xbf`) and formula-injection neutralized.

#### PDF Report Download
- **Path**: `GET /api/v1/reports/{dataset_id}/pdf`
- **Response `200 OK`**:
  - `Content-Type`: `application/pdf`
  - `Content-Disposition`: `attachment; filename="power_sub_report_<id8>_<YYYYMMDD>.pdf"`
  - Starts with binary `%PDF-`.
