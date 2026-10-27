"""Tests for datasets CRUD, cross-dataset isolation, malformed IDs, and TTL cleanup."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.database.connection import get_db
from app.database.models import DatasetRepository
from tests.data_factory import generate_synthetic_csv_bytes


def test_datasets_crud_and_isolation(client: TestClient):
    # 1. Upload Dataset A
    csv_bytes_a = generate_synthetic_csv_bytes()
    res_a = client.post(
        "/api/v1/upload", files={"file": ("dataset_a.csv", csv_bytes_a, "text/csv")}
    )
    assert res_a.status_code == 201
    id_a = res_a.json()["dataset_id"]

    # 2. Upload Dataset B
    csv_bytes_b = generate_synthetic_csv_bytes()
    res_b = client.post(
        "/api/v1/upload", files={"file": ("dataset_b.csv", csv_bytes_b, "text/csv")}
    )
    assert res_b.status_code == 201
    id_b = res_b.json()["dataset_id"]
    assert id_a != id_b

    # 3. List datasets
    list_res = client.get("/api/v1/datasets?limit=10&offset=0")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 2
    listed_ids = [item["id"] for item in list_data["items"]]
    assert id_a in listed_ids
    assert id_b in listed_ids

    # 4. Detail endpoint
    detail_res = client.get(f"/api/v1/datasets/{id_a}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == id_a
    assert detail_data["display_filename"] == "dataset_a.csv"

    # 5. Cross-Dataset Isolation test
    with get_db() as conn:
        df_a = DatasetRepository.get_records_df(conn, id_a)
        df_b = DatasetRepository.get_records_df(conn, id_b)

        # Cross check counts and records directly from DB queries
        cur_a = conn.execute(
            "SELECT COUNT(*) as cnt FROM energy_records WHERE dataset_id = ?", (id_a,)
        )
        cnt_a = cur_a.fetchone()["cnt"]

        cur_b = conn.execute(
            "SELECT COUNT(*) as cnt FROM energy_records WHERE dataset_id = ?", (id_b,)
        )
        cnt_b = cur_b.fetchone()["cnt"]

        assert len(df_a) == cnt_a
        assert len(df_b) == cnt_b

        # Prove query with id_a returns NO records belonging to id_b
        cross_check = conn.execute(
            "SELECT COUNT(*) as cnt FROM energy_records WHERE dataset_id = ? AND dataset_id = ?",
            (id_a, id_b),
        ).fetchone()["cnt"]
        assert cross_check == 0

    # 6. Delete Dataset A
    del_res = client.delete(f"/api/v1/datasets/{id_a}")
    assert del_res.status_code == 204

    # Subsequent GET returns 404
    assert client.get(f"/api/v1/datasets/{id_a}").status_code == 404

    # Verify cascading records removed from DB
    with get_db() as conn:
        records_after = conn.execute(
            "SELECT COUNT(*) as cnt FROM energy_records WHERE dataset_id = ?", (id_a,)
        ).fetchone()["cnt"]
        assert records_after == 0

    # Verify Dataset B is intact
    assert client.get(f"/api/v1/datasets/{id_b}").status_code == 200


def test_malformed_and_unknown_dataset_ids(client: TestClient):
    # Malformed UUID strings
    assert client.get("/api/v1/datasets/not-a-uuid").status_code == 404
    assert client.get("/api/v1/datasets/12345").status_code == 404
    assert client.get("/api/v1/datasets/../../etc/passwd").status_code == 404

    # Valid UUID format but non-existent
    unknown_uuid = str(uuid.uuid4())
    res = client.get(f"/api/v1/datasets/{unknown_uuid}")
    assert res.status_code == 404
    assert "not found" in res.json()["error"]["message"].lower()


def test_ttl_cleanup_functionality(client: TestClient):
    with get_db() as conn:
        # Create an expired dataset
        expired_id = str(uuid.uuid4())
        past_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        DatasetRepository.create_dataset(
            conn=conn,
            dataset_id=expired_id,
            display_filename="expired.csv",
            file_type="csv",
            record_count=10,
            quality={},
            column_info={},
            expires_at=past_time,
        )

        # Create an active dataset
        active_id = str(uuid.uuid4())
        future_time = (datetime.now(UTC) + timedelta(hours=24)).isoformat()
        DatasetRepository.create_dataset(
            conn=conn,
            dataset_id=active_id,
            display_filename="active.csv",
            file_type="csv",
            record_count=10,
            quality={},
            column_info={},
            expires_at=future_time,
        )

        # Run cleanup
        deleted_count = DatasetRepository.delete_expired_datasets(conn)
        assert deleted_count >= 1

    # Verify expired was deleted, active remains
    assert client.get(f"/api/v1/datasets/{expired_id}").status_code == 404
    assert client.get(f"/api/v1/datasets/{active_id}").status_code == 200
