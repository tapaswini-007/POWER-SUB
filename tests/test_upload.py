"""Integration tests for POST /api/v1/upload endpoint."""

import pandas as pd
from fastapi.testclient import TestClient

from tests.data_factory import (
    generate_image_only_pdf_bytes,
    generate_synthetic_csv_bytes,
    generate_synthetic_xls_bytes,
    generate_synthetic_xlsx_bytes,
)


def test_upload_valid_csv(client: TestClient):
    csv_bytes = generate_synthetic_csv_bytes()
    files = {"file": ("energy_report.csv", csv_bytes, "text/csv")}
    response = client.post("/api/v1/upload", files=files)

    assert response.status_code == 201
    data = response.json()
    assert "dataset_id" in data
    assert data["record_count"] > 0
    assert "data_quality" in data
    assert len(data["preview_rows"]) <= 10
    assert "Core Principle" in data["limitations"]
    assert "energy_kwh" in data["columns"]["mapped"].values()
    assert "date" in data["columns"]["mapped"].values()


def test_upload_valid_xlsx(client: TestClient):
    xlsx_bytes = generate_synthetic_xlsx_bytes()
    files = {
        "file": (
            "energy_report.xlsx",
            xlsx_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    response = client.post("/api/v1/upload", files=files)

    assert response.status_code == 201
    data = response.json()
    assert data["record_count"] > 0
    assert "dataset_id" in data


def test_upload_valid_xls(client: TestClient):
    xls_bytes = generate_synthetic_xls_bytes()
    files = {"file": ("energy_report.xls", xls_bytes, "application/vnd.ms-excel")}
    response = client.post("/api/v1/upload", files=files)

    assert response.status_code == 201
    data = response.json()
    assert data["record_count"] > 0


def test_upload_image_only_pdf_returns_422(client: TestClient):
    pdf_bytes = generate_image_only_pdf_bytes()
    files = {"file": ("scanned_invoice.pdf", pdf_bytes, "application/pdf")}
    response = client.post("/api/v1/upload", files=files)

    assert response.status_code == 422
    err = response.json()["error"]
    assert "OCR is not supported" in err["message"]


def test_upload_csv_missing_energy_column(client: TestClient):
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02"],
            "building": ["Building_A", "Building_A"],
            "cost": [100.0, 150.0],
        }
    )
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    files = {"file": ("no_energy.csv", csv_bytes, "text/csv")}
    response = client.post("/api/v1/upload", files=files)

    assert response.status_code == 422
    err = response.json()["error"]
    assert "No recognizable energy consumption column found" in err["message"]


def test_upload_energy_unit_conversion(client: TestClient):
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02"],
            "energy": [5000.0, 10000.0],  # In Wh
        }
    )
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    files = {"file": ("energy_wh.csv", csv_bytes, "text/csv")}
    data_form = {"energy_unit": "Wh"}
    response = client.post("/api/v1/upload", files=files, data=data_form)

    assert response.status_code == 201
    res = response.json()
    assert any("Wh to kWh" in w for w in res["warnings"])
    # 5000 Wh should be converted to 5.0 kWh
    assert res["preview_rows"][0]["energy_kwh"] == 5.0
    assert res["preview_rows"][1]["energy_kwh"] == 10.0


def test_upload_negative_energy_rejected(client: TestClient):
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "kwh": [100.0, -50.0, 120.0],
        }
    )
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    files = {"file": ("negative_energy.csv", csv_bytes, "text/csv")}
    response = client.post("/api/v1/upload", files=files)

    assert response.status_code == 201
    res = response.json()
    assert res["record_count"] == 2
    assert res["data_quality"]["rejected_rows"] == 1
    assert "negative_energy_consumption" in res["data_quality"]["rejection_reasons"]
