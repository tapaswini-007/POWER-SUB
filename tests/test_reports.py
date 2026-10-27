"""Tests for CSV and PDF report generation, content-types, and formula safety."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from tests.data_factory import generate_synthetic_csv_bytes


def test_csv_report_generation(client: TestClient):
    csv_bytes = generate_synthetic_csv_bytes()
    upload_res = client.post(
        "/api/v1/upload",
        files={"file": ("report_test.csv", csv_bytes, "text/csv")},
    )
    dataset_id = upload_res.json()["dataset_id"]

    res = client.get(f"/api/v1/reports/{dataset_id}/csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert f"power_sub_report_{dataset_id[:8]}" in res.headers["content-disposition"]

    # Must start with UTF-8 BOM
    content = res.content
    assert content.startswith(b"\xef\xbb\xbf")

    # Decodable CSV
    csv_text = content.decode("utf-8-sig")
    assert "energy_kwh" in csv_text
    assert "is_flagged_anomaly" in csv_text


def test_pdf_report_generation(client: TestClient):
    csv_bytes = generate_synthetic_csv_bytes()
    upload_res = client.post(
        "/api/v1/upload",
        files={"file": ("pdf_report_test.csv", csv_bytes, "text/csv")},
    )
    dataset_id = upload_res.json()["dataset_id"]

    res = client.get(f"/api/v1/reports/{dataset_id}/pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert f"power_sub_report_{dataset_id[:8]}" in res.headers["content-disposition"]

    # Must be valid PDF starting with %PDF-
    assert res.content.startswith(b"%PDF-")
    assert len(res.content) > 1000

    # Verify report was saved in REPORTS_DIR
    reports_dir = Path(settings.REPORTS_DIR)
    saved_files = list(reports_dir.glob(f"*{dataset_id[:8]}*.pdf"))
    assert len(saved_files) == 1


def test_report_unknown_dataset_404(client: TestClient):
    assert client.get("/api/v1/reports/00000000-0000-4000-8000-000000000000/csv").status_code == 404
    assert client.get("/api/v1/reports/00000000-0000-4000-8000-000000000000/pdf").status_code == 404
