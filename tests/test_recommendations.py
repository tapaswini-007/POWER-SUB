"""Tests for evidence-based recommendations and defensible savings calculations."""

import pandas as pd
from fastapi.testclient import TestClient

from tests.data_factory import generate_synthetic_csv_bytes


def test_recommendations_with_cost_data(client: TestClient):
    csv_bytes = generate_synthetic_csv_bytes()
    upload_res = client.post(
        "/api/v1/upload",
        files={"file": ("recs_test.csv", csv_bytes, "text/csv")},
    )
    dataset_id = upload_res.json()["dataset_id"]

    res = client.get(f"/api/v1/recommendations/{dataset_id}")
    assert res.status_code == 200
    data = res.json()

    assert data["dataset_id"] == dataset_id
    assert data["total_recommendations"] > 0
    assert "Core Principle" in data["limitations"]

    # Verify recommendations have supporting measurements with actual numbers
    for rec in data["recommendations"]:
        assert len(rec["supporting_measurements"]) > 0
        assert rec["priority"] in ("low", "medium", "high")
        assert rec["evidence_level"] in ("low", "medium", "high")
        assert len(rec["required_additional_data"]) > 0

    # Since synthetic sample has off-hours consumption, check for REC-OFFHOURS-001
    off_hours_rec = next((r for r in data["recommendations"] if "OFFHOURS" in r["id"]), None)
    assert off_hours_rec is not None
    assert off_hours_rec["estimated_savings"] is not None
    assert off_hours_rec["estimated_savings"]["potential_cost_savings"] > 0
    assert "potential, not guaranteed" in off_hours_rec["estimated_savings"]["confidence_label"]


def test_recommendations_without_cost_data_no_invented_savings(client: TestClient):
    # Dataset without cost column
    df_no_cost = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=30, freq="D").strftime("%Y-%m-%d"),
            "energy_kwh": [100.0, 105.0, 110.0] * 10,
            "operating_hours": [0.0, 8.0, 8.0] * 10,  # 10 days with 0 hours but ~100 kWh
        }
    )
    csv_bytes = df_no_cost.to_csv(index=False).encode("utf-8")
    upload_res = client.post(
        "/api/v1/upload",
        files={"file": ("no_cost.csv", csv_bytes, "text/csv")},
    )
    dataset_id = upload_res.json()["dataset_id"]

    # 1. Without tariff parameter: cost savings must NOT be invented
    res = client.get(f"/api/v1/recommendations/{dataset_id}")
    assert res.status_code == 200
    data = res.json()
    off_hours_rec = next((r for r in data["recommendations"] if "OFFHOURS" in r["id"]), None)
    assert off_hours_rec is not None
    assert off_hours_rec["estimated_savings"]["potential_cost_savings"] is None
    assert "Supply 'tariff_per_kwh'" in off_hours_rec["estimated_savings"]["note"]

    # 2. With explicit user tariff_per_kwh: cost savings computed from user tariff
    res_tariff = client.get(f"/api/v1/recommendations/{dataset_id}?tariff_per_kwh=0.20")
    assert res_tariff.status_code == 200
    tariff_data = res_tariff.json()
    off_hours_tariff = next(
        (r for r in tariff_data["recommendations"] if "OFFHOURS" in r["id"]), None
    )
    assert off_hours_tariff is not None
    assert off_hours_tariff["estimated_savings"]["potential_cost_savings"] > 0
    assert off_hours_tariff["estimated_savings"]["cost_source"] == "user_provided_tariff"


def test_recommendations_invalid_tariff(client: TestClient):
    csv_bytes = generate_synthetic_csv_bytes()
    upload_res = client.post(
        "/api/v1/upload",
        files={"file": ("tariff_check.csv", csv_bytes, "text/csv")},
    )
    dataset_id = upload_res.json()["dataset_id"]

    # Negative tariff -> 422
    assert (
        client.get(f"/api/v1/recommendations/{dataset_id}?tariff_per_kwh=-0.15").status_code == 422
    )
    # Zero tariff -> 422
    assert client.get(f"/api/v1/recommendations/{dataset_id}?tariff_per_kwh=0").status_code == 422
