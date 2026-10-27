"""Database data access helpers and models."""

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from app.core.errors import NotFoundError


class DatasetRepository:
    """Repository for managing datasets and associated energy records."""

    @staticmethod
    def create_dataset(
        conn: sqlite3.Connection,
        dataset_id: str,
        display_filename: str,
        file_type: str,
        record_count: int,
        quality: dict[str, Any],
        column_info: dict[str, Any],
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        created_at = datetime.now(UTC).isoformat()
        conn.execute(
            """
            INSERT INTO datasets (id, display_filename, file_type, created_at, expires_at, record_count, status, quality_json, column_info_json)
            VALUES (?, ?, ?, ?, ?, ?, 'ready', ?, ?)
            """,
            (
                dataset_id,
                display_filename,
                file_type,
                created_at,
                expires_at,
                record_count,
                json.dumps(quality),
                json.dumps(column_info),
            ),
        )
        return {
            "id": dataset_id,
            "display_filename": display_filename,
            "file_type": file_type,
            "created_at": created_at,
            "expires_at": expires_at,
            "record_count": record_count,
            "status": "ready",
            "quality": quality,
            "column_info": column_info,
        }

    @staticmethod
    def get_dataset(conn: sqlite3.Connection, dataset_id: str) -> dict[str, Any]:
        cursor = conn.execute(
            """
            SELECT id, display_filename, file_type, created_at, expires_at, record_count, status, quality_json, column_info_json
            FROM datasets
            WHERE id = ?
            """,
            (dataset_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Dataset with ID '{dataset_id}' not found.")

        return {
            "id": row["id"],
            "display_filename": row["display_filename"],
            "file_type": row["file_type"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "record_count": row["record_count"],
            "status": row["status"],
            "quality": json.loads(row["quality_json"]) if row["quality_json"] else {},
            "column_info": json.loads(row["column_info_json"]) if row["column_info_json"] else {},
        }

    @staticmethod
    def list_datasets(
        conn: sqlite3.Connection,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        cursor = conn.execute(
            """
            SELECT id, display_filename, file_type, created_at, expires_at, record_count, status, quality_json, column_info_json
            FROM datasets
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        results = []
        for row in cursor.fetchall():
            results.append(
                {
                    "id": row["id"],
                    "display_filename": row["display_filename"],
                    "file_type": row["file_type"],
                    "created_at": row["created_at"],
                    "expires_at": row["expires_at"],
                    "record_count": row["record_count"],
                    "status": row["status"],
                    "quality": json.loads(row["quality_json"]) if row["quality_json"] else {},
                    "column_info": json.loads(row["column_info_json"])
                    if row["column_info_json"]
                    else {},
                }
            )
        return results

    @staticmethod
    def count_datasets(conn: sqlite3.Connection) -> int:
        cursor = conn.execute("SELECT COUNT(*) AS cnt FROM datasets")
        return cursor.fetchone()["cnt"]

    @staticmethod
    def delete_dataset(conn: sqlite3.Connection, dataset_id: str) -> bool:
        """Delete dataset and cascading records."""
        # Ensure it exists
        DatasetRepository.get_dataset(conn, dataset_id)
        conn.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
        return True

    @staticmethod
    def delete_expired_datasets(conn: sqlite3.Connection) -> int:
        """Delete datasets whose expires_at is before current UTC time."""
        now_iso = datetime.now(UTC).isoformat()
        cursor = conn.execute(
            "DELETE FROM datasets WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now_iso,),
        )
        return cursor.rowcount

    @staticmethod
    def bulk_insert_records(
        conn: sqlite3.Connection,
        dataset_id: str,
        records: list[dict[str, Any]],
    ) -> None:
        """Insert records in batch inside current transaction."""
        if not records:
            return

        insert_sql = """
        INSERT INTO energy_records (
            dataset_id, row_id, date, energy_kwh, building, department,
            equipment, cost, temperature, operating_hours, was_corrected
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        rows = [
            (
                dataset_id,
                r.get("row_id", idx),
                r.get("date"),
                float(r["energy_kwh"]) if r.get("energy_kwh") is not None else 0.0,
                r.get("building"),
                r.get("department"),
                r.get("equipment"),
                float(r["cost"]) if r.get("cost") is not None else None,
                float(r["temperature"]) if r.get("temperature") is not None else None,
                float(r["operating_hours"]) if r.get("operating_hours") is not None else None,
                1 if r.get("was_corrected") else 0,
            )
            for idx, r in enumerate(records)
        ]
        conn.executemany(insert_sql, rows)

    @staticmethod
    def get_records_df(
        conn: sqlite3.Connection,
        dataset_id: str,
    ) -> pd.DataFrame:
        """Fetch all cleaned records for a dataset as a Pandas DataFrame."""
        # Validate existence
        DatasetRepository.get_dataset(conn, dataset_id)

        query = """
        SELECT row_id, date, energy_kwh, building, department, equipment,
               cost, temperature, operating_hours, was_corrected
        FROM energy_records
        WHERE dataset_id = ?
        ORDER BY row_id ASC
        """
        df = pd.read_sql_query(query, conn, params=(dataset_id,))
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    @staticmethod
    def get_records_page(
        conn: sqlite3.Connection,
        dataset_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        DatasetRepository.get_dataset(conn, dataset_id)
        cursor = conn.execute(
            """
            SELECT row_id, date, energy_kwh, building, department, equipment,
                   cost, temperature, operating_hours, was_corrected
            FROM energy_records
            WHERE dataset_id = ?
            ORDER BY row_id ASC
            LIMIT ? OFFSET ?
            """,
            (dataset_id, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]


class AnalysisRepository:
    """Repository for analysis and anomaly results caching."""

    @staticmethod
    def save_analysis(
        conn: sqlite3.Connection,
        dataset_id: str,
        baseline_method: str,
        params: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        created_at = datetime.now(UTC).isoformat()
        conn.execute(
            """
            INSERT INTO analysis_results (dataset_id, baseline_method, params_json, result_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                dataset_id,
                baseline_method,
                json.dumps(params, sort_keys=True),
                json.dumps(result),
                created_at,
            ),
        )

    @staticmethod
    def get_cached_anomaly_result(
        conn: sqlite3.Connection,
        dataset_id: str,
        params_hash: str,
    ) -> dict[str, Any] | None:
        cursor = conn.execute(
            """
            SELECT model_info_json, result_json, created_at
            FROM anomaly_results
            WHERE dataset_id = ? AND params_hash = ?
            ORDER BY id DESC LIMIT 1
            """,
            (dataset_id, params_hash),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "model_info": json.loads(row["model_info_json"]),
            "result": json.loads(row["result_json"]),
            "created_at": row["created_at"],
        }

    @staticmethod
    def get_latest_anomaly_result(
        conn: sqlite3.Connection,
        dataset_id: str,
    ) -> dict[str, Any] | None:
        cursor = conn.execute(
            """
            SELECT params_json, model_info_json, result_json, created_at
            FROM anomaly_results
            WHERE dataset_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (dataset_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "params": json.loads(row["params_json"]),
            "model_info": json.loads(row["model_info_json"]),
            "result": json.loads(row["result_json"]),
            "created_at": row["created_at"],
        }

    @staticmethod
    def save_anomaly_result(
        conn: sqlite3.Connection,
        dataset_id: str,
        params: dict[str, Any],
        params_hash: str,
        model_info: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        created_at = datetime.now(UTC).isoformat()
        conn.execute(
            """
            INSERT INTO anomaly_results (dataset_id, params_json, params_hash, model_info_json, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                dataset_id,
                json.dumps(params, sort_keys=True),
                params_hash,
                json.dumps(model_info),
                json.dumps(result),
                created_at,
            ),
        )
