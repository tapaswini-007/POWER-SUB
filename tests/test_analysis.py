"""Tests for energy consumption analysis, baselines, and zero-baseline safety."""

import pandas as pd
from fastapi.testclient import TestClient

from app.services.energy_analysis import calculate_baseline
from tests.data_factory import generate_synthetic_csv_bytes


def test_energy_analysis_endpoint(client: TestClient):
    csv_bytes = generate_synthetic_csv_bytes()
    upload_res = client.post(
        "/api/v1/upload",
        files={"file": ("analysis_test.csv", csv_bytes, "text/csv")},
    )
    dataset_id = upload_res.json()["dataset_id"]

    # Call analysis endpoint
    res = client.get(f"/api/v1/analysis/{dataset_id}?baseline_method=historical_mean")
    assert res.status_code == 200
    data = res.json()

    assert data["dataset_id"] == dataset_id
    stats = data["statistics"]
    assert stats["total_kwh"] > 0
    assert stats["mean_kwh"] > 0
    assert stats["median_kwh"] > 0

    # Baseline comparison check
    baseline = data["baseline_comparison"]
    assert baseline["baseline_method_used"] == "historical_mean"
    assert baseline["baseline_kwh"] > 0
    assert baseline["overall_deviation_pct"] is not None

    # Cost statistics check
    cost = data["cost_statistics"]
    assert cost["has_cost_data"] is True
    assert cost["total_cost"] > 0
    assert cost["derived_cost_per_kwh"] > 0

    # Injected outlier records detected in high consumption list
    high_records = data["high_consumption_records"]
    assert len(high_records) > 0
    # Top record should be our injected 450 kWh spike
    top_record = high_records[0]
    assert top_record["energy_kwh"] >= 280.0


def test_baseline_methods(client: TestClient):
    csv_bytes = generate_synthetic_csv_bytes()
    upload_res = client.post(
        "/api/v1/upload",
        files={"file": ("baselines_test.csv", csv_bytes, "text/csv")},
    )
    dataset_id = upload_res.json()["dataset_id"]

    # historical_median
    res_med = client.get(f"/api/v1/analysis/{dataset_id}?baseline_method=historical_median")
    assert res_med.status_code == 200
    assert res_med.json()["baseline_comparison"]["baseline_method_used"] == "historical_median"

    # rolling_average
    res_roll = client.get(f"/api/v1/analysis/{dataset_id}?baseline_method=rolling_average")
    assert res_roll.status_code == 200
    assert res_roll.json()["baseline_comparison"]["baseline_method_used"] == "rolling_average"

    # user_target valid
    res_target = client.get(
        f"/api/v1/analysis/{dataset_id}?baseline_method=user_target&target_kwh=100.0"
    )
    assert res_target.status_code == 200
    target_data = res_target.json()["baseline_comparison"]
    assert target_data["baseline_kwh"] == 100.0

    # user_target missing target_kwh -> 400
    res_invalid_target = client.get(f"/api/v1/analysis/{dataset_id}?baseline_method=user_target")
    assert res_invalid_target.status_code == 400

    # user_target <= 0 -> 400
    res_zero_target = client.get(
        f"/api/v1/analysis/{dataset_id}?baseline_method=user_target&target_kwh=0"
    )
    assert res_zero_target.status_code == 400


def test_zero_baseline_prevention_of_division_by_zero():
    # DataFrame with 0 consumption everywhere
    df_zero = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=10, freq="D"),
            "energy_kwh": [0.0] * 10,
        }
    )

    baseline_val, _method_used, dev_pct, status_note = calculate_baseline(
        df=df_zero,
        method="historical_mean",
    )

    # Must be 0.0, dev_pct must be None (never Inf or NaN), explanation provided
    assert baseline_val == 0.0
    assert dev_pct is None
    assert "division by zero" in status_note.lower()
