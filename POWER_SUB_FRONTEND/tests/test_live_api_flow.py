"""
End-to-End Live API Integration Test
Tests the full lifecycle exactly as executed by the frontend pages:
Upload -> Dataset List -> Analysis -> Anomalies Run -> Recommendations -> PDF/CSV Reports -> Delete.
"""

import os
import urllib.request
import json
import mimetypes
import uuid

API_BASE = "http://127.0.0.1:8000"
FRONTEND_BASE = "http://127.0.0.1:5173"
SAMPLE_CSV = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sample_data", "sample_energy.csv"))


def post_multipart(url, file_path, field_name="file"):
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    filename = os.path.basename(file_path)
    mime = mimetypes.guess_type(file_path)[0] or "text/csv"

    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8"),
        f"Content-Type: {mime}\r\n\r\n".encode("utf-8"),
        file_bytes,
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    body = b"".join(parts)

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Origin", "http://127.0.0.1:5173")

    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def test_live_lifecycle():
    print("==================================================")
    print("STARTING LIVE POWER-SUB E2E LIFECYCLE VERIFICATION")
    print("==================================================")

    # 1. Health check
    with urllib.request.urlopen(f"{API_BASE}/api/v1/health") as r:
        health = json.loads(r.read().decode("utf-8"))
        assert health["status"] == "healthy"
        print("1. [PASS] Health check verified:", health["status"], f"(v{health['version']})")

    # 2. Upload sample CSV
    upload_status, upload_res = post_multipart(f"{API_BASE}/api/v1/upload", SAMPLE_CSV)
    assert upload_status == 201
    dataset_id = upload_res["dataset_id"]
    record_count = upload_res["record_count"]
    assert dataset_id and record_count > 0
    print(f"2. [PASS] Real upload successful. Dataset ID: {dataset_id}, Records: {record_count}")

    # 3. List datasets
    with urllib.request.urlopen(f"{API_BASE}/api/v1/datasets") as r:
        ds_list = json.loads(r.read().decode("utf-8"))
        assert any((d.get("dataset_id") or d.get("id")) == dataset_id for d in ds_list["items"])
        print(f"3. [PASS] Dataset history lists newly uploaded dataset. Total items: {ds_list['total']}")

    # 4. Energy Analysis
    with urllib.request.urlopen(f"{API_BASE}/api/v1/analysis/{dataset_id}?baseline_method=historical_mean") as r:
        analysis = json.loads(r.read().decode("utf-8"))
        assert "summary" in analysis
        assert "baseline" in analysis
        total_kwh = analysis["summary"]["total_consumption_kwh"]
        print(f"4. [PASS] Energy analysis verified. Total consumption: {total_kwh:.2f} kWh")

    # 5. Run AI Anomalies (POST)
    req = urllib.request.Request(f"{API_BASE}/api/v1/anomalies/{dataset_id}?contamination=0.05", data=b"", method="POST")
    req.add_header("Origin", "http://127.0.0.1:5173")
    with urllib.request.urlopen(req) as r:
        anomaly_res = json.loads(r.read().decode("utf-8"))
        flagged = anomaly_res["anomalies_detected"]
        pct = anomaly_res["anomaly_percentage"]
        method = anomaly_res["model_info"]["method"]
        print(f"5. [PASS] AI Anomaly Detection ran successfully. Method: '{method}', Flagged: {flagged} ({pct:.1f}%)")

    # 6. Fetch Recommendations
    with urllib.request.urlopen(f"{API_BASE}/api/v1/recommendations/{dataset_id}?tariff_per_kwh=8.5") as r:
        recs = json.loads(r.read().decode("utf-8"))
        assert "recommendations" in recs
        print(f"6. [PASS] Recommendations generated. Count: {len(recs['recommendations'])}")

    # 7. Download PDF Report
    with urllib.request.urlopen(f"{API_BASE}/api/v1/reports/{dataset_id}/pdf") as r:
        pdf_bytes = r.read()
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b"%PDF")
        print(f"7. [PASS] PDF report generation verified. Size: {len(pdf_bytes)} bytes")

    # 8. Download CSV Report
    with urllib.request.urlopen(f"{API_BASE}/api/v1/reports/{dataset_id}/csv") as r:
        csv_text = r.read().decode("utf-8")
        assert len(csv_text) > 100
        assert "anomaly_score" in csv_text
        print(f"8. [PASS] CSV anomalies callset verified. Size: {len(csv_text)} characters")

    # 9. Clean up dataset (DELETE)
    del_req = urllib.request.Request(f"{API_BASE}/api/v1/datasets/{dataset_id}", method="DELETE")
    del_req.add_header("Origin", "http://127.0.0.1:5173")
    with urllib.request.urlopen(del_req) as r:
        del_res = json.loads(r.read().decode("utf-8"))
        assert del_res["status"] == "success"
        print(f"9. [PASS] Dataset deletion verified. Dataset {dataset_id} removed cleanly.")

    print("==================================================")
    print("ALL 9 REAL API WORKFLOW GATES PASSED 100% SUCCESFULLY")
    print("==================================================")


if __name__ == "__main__":
    test_live_lifecycle()
