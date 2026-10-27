"""AI-based and rule-based anomaly detection service using IsolationForest and robust statistics."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

from app.core.config import settings
from app.core.errors import BadRequestError

ALLOWED_RAW_FEATURES = {"energy_kwh", "operating_hours", "cost", "temperature"}


def generate_params_hash(params: dict[str, Any]) -> str:
    """Create a deterministic SHA-256 hash for anomaly detection parameters."""
    serialized = json.dumps(params, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def engineer_features(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Build derived numeric features strictly excluding identifiers, raw dates, and IDs."""
    feats_df = pd.DataFrame(index=df.index)
    dropped: dict[str, str] = {}

    # 1. Allowed Raw Features
    for col in ["energy_kwh", "operating_hours", "cost", "temperature"]:
        if col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce")
            missing_pct = series.isna().mean()
            if missing_pct > 0.5:
                dropped[col] = f"Dropped due to excessive missing values ({missing_pct:.1%})"
            elif series.dropna().nunique() <= 1:
                dropped[col] = "Dropped because feature is constant across records"
            else:
                feats_df[col] = series

    # 2. Meaningful cyclical time features (derived from date, never using raw timestamps)
    if "date" in df.columns and pd.api.types.is_datetime64_any_dtype(df["date"]):
        # Day of week cyclical (0 = Monday, 6 = Sunday)
        dow = df["date"].dt.dayofweek
        feats_df["dow_sin"] = np.sin(2.0 * np.pi * dow / 7.0)
        feats_df["dow_cos"] = np.cos(2.0 * np.pi * dow / 7.0)

        # Month cyclical (1 to 12)
        month = df["date"].dt.month
        feats_df["month_sin"] = np.sin(2.0 * np.pi * (month - 1) / 12.0)
        feats_df["month_cos"] = np.cos(2.0 * np.pi * (month - 1) / 12.0)

    # 3. Energy per operating hour (guarding against division by zero)
    if "operating_hours" in feats_df.columns and "energy_kwh" in feats_df.columns:
        hours_safe = feats_df["operating_hours"].fillna(0.0).clip(lower=0.5)
        feats_df["energy_per_op_hour"] = feats_df["energy_kwh"] / hours_safe

    # 4. Rolling deviation from 7-day median
    if "energy_kwh" in feats_df.columns and len(feats_df) >= 7:
        rolling_med = feats_df["energy_kwh"].rolling(window=7, min_periods=1).median()
        feats_df["rolling_energy_dev"] = feats_df["energy_kwh"] - rolling_med

    return feats_df, dropped


def identify_contributing_features(
    row_features: pd.Series,
    feature_medians: pd.Series,
    feature_scales: pd.Series,
    top_n: int = 3,
) -> list[dict[str, Any]]:
    """Determine top contributing features via robust z-score deviation from dataset median."""
    deviations = []
    for feat in row_features.index:
        val = row_features[feat]
        med = feature_medians[feat]
        scale = feature_scales[feat]

        if pd.isna(val) or pd.isna(med):
            continue

        z = (val - med) / (scale if scale > 1e-6 else 1.0)
        direction = "higher" if z >= 0 else "lower"
        deviations.append(
            {
                "feature": str(feat),
                "actual_value": round(float(val), 2),
                "dataset_median": round(float(med), 2),
                "deviation": round(float(abs(z)), 2),
                "direction": direction,
            }
        )

    # Sort descending by absolute deviation
    deviations.sort(key=lambda x: x["deviation"], reverse=True)
    return deviations[:top_n]


def run_rule_based_iqr_fallback(
    df: pd.DataFrame,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Fallback rule-based outlier detection using Interquartile Range (IQR)."""
    series = df["energy_kwh"].dropna()
    if len(series) < 3:
        q25 = q75 = med = float(series.median()) if not series.empty else 0.0
        iqr = 0.0
    else:
        q25, q75 = np.percentile(series, [25, 75])
        iqr = float(q75 - q25)
        med = float(series.median())

    upper_bound = q75 + 1.5 * iqr

    records = []
    flagged_cnt = 0
    severity_counts = {"low": 0, "medium": 0, "high": 0, "normal": 0}

    for _, row in df.iterrows():
        act = float(row["energy_kwh"])
        is_anom = bool(act > upper_bound and iqr > 1e-6)
        if is_anom:
            flagged_cnt += 1
            severity = "high" if act > (q75 + 3.0 * iqr) else "medium"
            severity_counts[severity] += 1
            score = round(float((act - med) / (iqr if iqr > 1e-6 else 1.0)), 2)
        else:
            severity = "normal"
            severity_counts["normal"] += 1
            score = 0.0

        dt_str = (
            row["date"].strftime("%Y-%m-%d")
            if hasattr(row["date"], "strftime")
            else str(row["date"])
        )

        records.append(
            {
                "row_id": int(row.get("row_id", 0)),
                "date": dt_str,
                "energy_kwh": round(act, 2),
                "building": str(row["building"]) if pd.notna(row.get("building")) else None,
                "department": str(row["department"]) if pd.notna(row.get("department")) else None,
                "equipment": str(row["equipment"]) if pd.notna(row.get("equipment")) else None,
                "is_anomaly": is_anom,
                "anomaly_score": score,
                "severity": severity,
                "contributing_features": [
                    {
                        "feature": "energy_kwh",
                        "actual_value": round(act, 2),
                        "dataset_median": round(med, 2),
                        "deviation": score,
                        "direction": "higher" if act >= med else "lower",
                    }
                ]
                if is_anom
                else [],
            }
        )

    summary = {
        "total_records": len(df),
        "anomalies_flagged": flagged_cnt,
        "anomaly_percentage": round((flagged_cnt / len(df)) * 100.0, 2) if len(df) > 0 else 0.0,
        "severity_counts": severity_counts,
    }

    return summary, records


def detect_anomalies(
    df: pd.DataFrame,
    contamination: float | None = None,
    sensitivity: str | None = None,
    n_estimators: int = 200,
    max_samples: Any = "auto",
    random_state: int | None = None,
    features: list[str] | None = None,
    use_rule_fallback: bool = True,
) -> dict[str, Any]:
    """Execute AI-based IsolationForest anomaly detection with rule-based fallback."""
    seed = random_state if random_state is not None else settings.RANDOM_SEED

    # Resolve sensitivity to contamination
    contam = contamination
    if contam is None:
        if sensitivity == "low":
            contam = 0.02
        elif sensitivity == "medium":
            contam = 0.05
        elif sensitivity == "high":
            contam = 0.10
        else:
            contam = settings.DEFAULT_CONTAMINATION

    if not (0.001 <= contam <= 0.5):
        raise BadRequestError("Contamination must be between 0.001 and 0.5.")

    # 1. Feature Engineering
    raw_feats_df, dropped_feats = engineer_features(df)

    # Filter to requested features if provided
    if features:
        invalid_feats = [
            f for f in features if f not in raw_feats_df.columns and f not in ALLOWED_RAW_FEATURES
        ]
        if invalid_feats:
            raise BadRequestError(
                f"Requested features {invalid_feats} are not in allowed feature set: "
                f"{list(ALLOWED_RAW_FEATURES)}"
            )
        usable_cols = [c for c in features if c in raw_feats_df.columns]
        raw_feats_df = raw_feats_df[usable_cols]

    usable_features = list(raw_feats_df.columns)

    # 2. Insufficient Data Check (< MIN_RECORDS_FOR_ML or < 1 usable feature)
    if len(df) < settings.MIN_RECORDS_FOR_ML or len(usable_features) < 1:
        msg = (
            f"Dataset has {len(df)} record(s) and {len(usable_features)} usable feature(s). "
            f"A minimum of {settings.MIN_RECORDS_FOR_ML} records is required for AI model training."
        )

        if use_rule_fallback and "energy_kwh" in df.columns:
            summary, records = run_rule_based_iqr_fallback(df)
            model_info = {
                "algorithm": "Interquartile Range (IQR) Fallback",
                "method": "rule_based_iqr",
                "parameters": {"multiplier": 1.5},
                "features_used": ["energy_kwh"],
                "features_dropped": dropped_feats,
                "n_records": len(df),
                "random_seed": seed,
                "trained_at": datetime.now(UTC).isoformat(),
            }
            return {
                "status": "insufficient_data",
                "message": f"{msg} Provided rule_based_iqr fallback results.",
                "model_info": model_info,
                "summary": summary,
                "anomalies": records,
            }
        else:
            empty_summary = {
                "total_records": len(df),
                "anomalies_flagged": 0,
                "anomaly_percentage": 0.0,
                "severity_counts": {
                    "low": 0,
                    "medium": 0,
                    "high": 0,
                    "normal": len(df),
                },
            }
            model_info = {
                "algorithm": "None",
                "method": "rule_based_iqr",
                "parameters": {},
                "features_used": [],
                "features_dropped": dropped_feats,
                "n_records": len(df),
                "random_seed": seed,
                "trained_at": datetime.now(UTC).isoformat(),
            }
            return {
                "status": "insufficient_data",
                "message": msg,
                "model_info": model_info,
                "summary": empty_summary,
                "anomalies": [],
            }

    # 3. Fit IsolationForest Pipeline
    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", RobustScaler()),
            (
                "model",
                IsolationForest(
                    contamination=contam,
                    n_estimators=n_estimators,
                    max_samples=max_samples,
                    random_state=seed,
                    n_jobs=1,
                ),
            ),
        ]
    )

    pipeline.fit(raw_feats_df)

    # Transform decision_function: sklearn returns lower values for anomalies (negative).
    # We negate it so higher values indicate greater anomaly severity.
    raw_scores = -pipeline.decision_function(raw_feats_df)
    preds = pipeline.predict(raw_feats_df)  # -1 = anomaly, 1 = normal
    is_anomaly_mask = preds == -1

    # Compute feature medians and scale for explanations
    feat_medians = raw_feats_df.median()
    feat_scales = (raw_feats_df - feat_medians).abs().median() / 0.6745
    feat_scales = feat_scales.replace(0.0, 1.0)

    # Determine severity quantiles for anomalous records
    anom_scores = raw_scores[is_anomaly_mask]
    q_high = float(np.percentile(anom_scores, 75)) if len(anom_scores) > 0 else 0.5
    q_med = float(np.percentile(anom_scores, 25)) if len(anom_scores) > 0 else 0.2

    records: list[dict[str, Any]] = []
    severity_counts = {"low": 0, "medium": 0, "high": 0, "normal": 0}

    for idx, (_, row) in enumerate(df.iterrows()):
        is_anom = bool(is_anomaly_mask[idx])
        score = round(float(raw_scores[idx]), 4)

        if is_anom:
            if score >= q_high:
                severity = "high"
            elif score >= q_med:
                severity = "medium"
            else:
                severity = "low"
            severity_counts[severity] += 1
            contributing = identify_contributing_features(
                raw_feats_df.iloc[idx],
                feat_medians,
                feat_scales,
            )
        else:
            severity = "normal"
            severity_counts["normal"] += 1
            contributing = []

        dt_str = (
            row["date"].strftime("%Y-%m-%d")
            if hasattr(row["date"], "strftime")
            else str(row["date"])
        )

        records.append(
            {
                "row_id": int(row.get("row_id", idx + 1)),
                "date": dt_str,
                "energy_kwh": round(float(row["energy_kwh"]), 2),
                "building": str(row["building"]) if pd.notna(row.get("building")) else None,
                "department": str(row["department"]) if pd.notna(row.get("department")) else None,
                "equipment": str(row["equipment"]) if pd.notna(row.get("equipment")) else None,
                "is_anomaly": is_anom,
                "anomaly_score": score,
                "severity": severity,
                "contributing_features": contributing,
            }
        )

    flagged_count = int(is_anomaly_mask.sum())
    summary = {
        "total_records": len(df),
        "anomalies_flagged": flagged_count,
        "anomaly_percentage": round((flagged_count / len(df)) * 100.0, 2),
        "severity_counts": severity_counts,
    }

    model_info = {
        "algorithm": "scikit-learn IsolationForest",
        "method": "ai_isolation_forest",
        "parameters": {
            "contamination": contam,
            "n_estimators": n_estimators,
            "max_samples": str(max_samples),
            "random_state": seed,
        },
        "features_used": usable_features,
        "features_dropped": dropped_feats,
        "n_records": len(df),
        "random_seed": seed,
        "trained_at": datetime.now(UTC).isoformat(),
    }

    return {
        "status": "completed",
        "message": f"Successfully executed IsolationForest anomaly detection on {len(df)} records.",
        "model_info": model_info,
        "summary": summary,
        "anomalies": records,
    }
