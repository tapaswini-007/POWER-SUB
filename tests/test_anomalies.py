"""Tests for AI-based anomaly detection, determinism, fallback, and feature sanitization."""

import pandas as pd
from fastapi.testclient import TestClient

from app.services.anomaly_detection import engineer_features
from tests.data_factory import generate_synthetic_csv_bytes


def test_anomaly_detection_with_sufficient_data(client: TestClient):
    csv_bytes = generate_synthetic_csv_bytes()
    upload_res = client.post(
        "/api/v1/upload",
        files={"file": ("anom_test.csv", csv_bytes, "text/csv")},
    )
    dataset_id = upload_res.json()["dataset_id"]

    # 1. Trigger AI detection
    payload = {
        "sensitivity": "medium",
        "n_estimators": 100,
        "random_state": 42,
    }
    res = client.post(f"/api/v1/anomalies/{dataset_id}", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "completed"
    assert data["model_info"]["method"] == "ai_isolation_forest"
    assert data["summary"]["anomalies_flagged"] > 0
    assert "Core Principle" in data["limitations"]

    # Injected outlier row 15 (450 kWh) should be flagged
    anomalies = [a for a in data["anomalies"] if a["is_anomaly"]]
    high_kwh_anoms = [a for a in anomalies if a["energy_kwh"] >= 280.0]
    assert len(high_kwh_anoms) >= 1

    # Check contributing features exist on flagged records
    assert len(anomalies[0]["contributing_features"]) > 0

    # 2. Test Determinism and Caching: same request returns cached result with identical flags
    res_cached = client.post(f"/api/v1/anomalies/{dataset_id}", json=payload)
    assert res_cached.status_code == 200
    assert "[Cached Result]" in res_cached.json()["message"]
    assert res_cached.json()["summary"] == data["summary"]

    # 3. Test GET endpoint
    get_res = client.get(f"/api/v1/anomalies/{dataset_id}?only_anomalies=true&limit=10")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert all(a["is_anomaly"] for a in get_data["anomalies"])
    assert len(get_data["anomalies"]) <= 10


def test_insufficient_data_iqr_fallback(client: TestClient):
    # Only 10 records (< MIN_RECORDS_FOR_ML = 30)
    df_small = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=10, freq="D").strftime("%Y-%m-%d"),
            "energy_kwh": [10.0, 11.0, 12.0, 10.5, 11.2, 10.8, 12.1, 11.0, 95.0, 10.9],
        }
    )
    csv_bytes = df_small.to_csv(index=False).encode("utf-8")
    upload_res = client.post(
        "/api/v1/upload",
        files={"file": ("small.csv", csv_bytes, "text/csv")},
    )
    dataset_id = upload_res.json()["dataset_id"]

    res = client.post(
        f"/api/v1/anomalies/{dataset_id}",
        json={"use_rule_fallback": True},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "insufficient_data"
    assert data["model_info"]["method"] == "rule_based_iqr"
    # Injected spike of 95.0 should be flagged by IQR
    flagged = [a for a in data["anomalies"] if a["is_anomaly"]]
    assert len(flagged) == 1
    assert flagged[0]["energy_kwh"] == 95.0


def test_feature_exclusion_guarantee():
    # Verify that raw date, IDs, row numbers, and text names are NEVER used in features
    df = pd.DataFrame(
        {
            "row_id": [1, 2, 3],
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "building": ["Building_A", "Building_B", "Building_C"],
            "equipment": ["M1", "M2", "M3"],
            "energy_kwh": [100.0, 120.0, 110.0],
            "operating_hours": [8.0, 8.5, 9.0],
        }
    )

    feats_df, _dropped = engineer_features(df)

    # Excluded columns check
    for forbidden in ["row_id", "date", "building", "equipment", "department"]:
        assert forbidden not in feats_df.columns

    # Allowed derived features check
    assert "energy_kwh" in feats_df.columns
    assert "operating_hours" in feats_df.columns
    assert "dow_sin" in feats_df.columns
    assert "dow_cos" in feats_df.columns


def test_contamination_validation(client: TestClient):
    csv_bytes = generate_synthetic_csv_bytes()
    upload_res = client.post(
        "/api/v1/upload",
        files={"file": ("contam_test.csv", csv_bytes, "text/csv")},
    )
    dataset_id = upload_res.json()["dataset_id"]

    # Contamination too high (> 0.5) -> 422
    res_high = client.post(
        f"/api/v1/anomalies/{dataset_id}",
        json={"contamination": 0.8},
    )
    assert res_high.status_code == 422

    # Contamination too low (< 0.001) -> 422
    res_low = client.post(
        f"/api/v1/anomalies/{dataset_id}",
        json={"contamination": 0.00001},
    )
    assert res_low.status_code == 422
