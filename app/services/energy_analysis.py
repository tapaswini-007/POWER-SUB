"""Service for energy consumption statistics, baseline calculations, and robust outlier detection."""

from typing import Any

import numpy as np
import pandas as pd

from app.core.errors import BadRequestError


def compute_robust_z_scores(series: pd.Series) -> tuple[pd.Series, float, float]:
    """Compute robust z-scores using Median and Median Absolute Deviation (MAD).

    robust_z = 0.6745 * (x - median) / MAD
    Returns: (z_scores, median_val, scale_val)
    """
    clean = series.dropna()
    if len(clean) < 3:
        return (
            pd.Series(0.0, index=series.index),
            float(clean.median()) if not clean.empty else 0.0,
            1.0,
        )

    med = float(clean.median())
    abs_dev = (clean - med).abs()
    mad = float(abs_dev.median())

    if mad > 1e-6:
        scale = mad / 0.6745
        z_scores = (series - med) / scale
    else:
        # Fallback to Interquartile Range (IQR) if MAD is zero
        q75, q25 = np.percentile(clean, [75, 25])
        iqr = float(q75 - q25)
        if iqr > 1e-6:
            scale = iqr / 1.349
            z_scores = (series - med) / scale
        else:
            std = float(clean.std())
            if std > 1e-6:
                z_scores = (series - med) / std
                scale = std
            else:
                z_scores = pd.Series(0.0, index=series.index)
                scale = 1.0

    return z_scores.fillna(0.0), med, scale


def calculate_baseline(
    df: pd.DataFrame,
    method: str = "historical_mean",
    target_kwh: float | None = None,
    group_by: str | None = None,
) -> tuple[float, str, float | None, str]:
    """Compute baseline kWh and overall percentage deviation.

    Returns:
        (baseline_kwh, baseline_method_used, overall_deviation_pct, baseline_status)
    """
    if df.empty or "energy_kwh" not in df.columns:
        return 0.0, method, None, "Insufficient data to calculate baseline."

    actual_series = df["energy_kwh"].dropna()
    if actual_series.empty:
        return 0.0, method, None, "No non-empty energy consumption values found."

    mean_val = float(actual_series.mean())
    median_val = float(actual_series.median())

    method_used = method
    baseline_val: float = mean_val
    status_note = "Baseline successfully calculated."

    if method == "historical_mean":
        baseline_val = mean_val
    elif method == "historical_median":
        baseline_val = median_val
    elif method == "rolling_average":
        if len(df) >= 7:
            # 7-period rolling average mean
            rolling = actual_series.rolling(window=7, min_periods=1).mean()
            baseline_val = float(rolling.mean())
        else:
            baseline_val = mean_val
            method_used = "historical_mean"
            status_note = (
                "Insufficient records for 7-period rolling average; fell back to historical_mean."
            )
    elif method == "same_period_average":
        if "date" in df.columns and len(df) >= 14:
            # Group by day of week
            dow_means = df.groupby(df["date"].dt.dayofweek)["energy_kwh"].mean()
            baseline_val = float(dow_means.mean())
        else:
            baseline_val = mean_val
            method_used = "historical_mean"
            status_note = (
                "Insufficient date history for same_period_average; fell back to historical_mean."
            )
    elif method == "user_target":
        if target_kwh is None or target_kwh <= 0:
            raise BadRequestError(
                "When using 'user_target' baseline_method, 'target_kwh' must be > 0."
            )
        baseline_val = float(target_kwh)
    else:
        baseline_val = mean_val
        method_used = "historical_mean"
        status_note = f"Unrecognized baseline method '{method}'; fell back to historical_mean."

    # Prevent division by zero: check if baseline_val is zero or NaN
    if np.isnan(baseline_val) or abs(baseline_val) < 1e-9:
        return (
            0.0,
            method_used,
            None,
            "Baseline value is zero or undefined; percentage deviation cannot be computed to prevent division by zero.",
        )

    # Average actual per record vs baseline per record
    avg_actual = float(actual_series.mean())
    dev_pct = round(((avg_actual - baseline_val) / baseline_val) * 100.0, 2)

    return round(baseline_val, 4), method_used, dev_pct, status_note


def analyze_energy_dataset(
    df: pd.DataFrame,
    baseline_method: str = "historical_mean",
    target_kwh: float | None = None,
    group_by: str | None = None,
    granularity: str | None = None,
    quality_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute complete descriptive analysis, cost calculation, and baseline comparison."""
    if df.empty:
        raise BadRequestError("Cannot analyze an empty dataset.")

    energy = df["energy_kwh"].dropna()
    total_kwh = round(float(energy.sum()), 2)
    mean_kwh = round(float(energy.mean()), 2)
    median_kwh = round(float(energy.median()), 2)
    min_kwh = round(float(energy.min()), 2)
    max_kwh = round(float(energy.max()), 2)
    std_kwh = round(float(energy.std()), 2) if len(energy) > 1 else 0.0

    stats = {
        "total_kwh": total_kwh,
        "mean_kwh": mean_kwh,
        "median_kwh": median_kwh,
        "min_kwh": min_kwh,
        "max_kwh": max_kwh,
        "std_kwh": std_kwh,
    }

    # Cost statistics derived strictly from data
    cost_stats: dict[str, Any] = {
        "has_cost_data": False,
        "total_cost": None,
        "average_cost_per_entry": None,
        "derived_cost_per_kwh": None,
        "note": "No cost column present in dataset.",
    }
    if "cost" in df.columns and df["cost"].notna().any():
        cost_series = df["cost"].dropna()
        total_cost = float(cost_series.sum())
        cost_stats["has_cost_data"] = True
        cost_stats["total_cost"] = round(total_cost, 2)
        cost_stats["average_cost_per_entry"] = round(float(cost_series.mean()), 2)
        if total_kwh > 0:
            cost_stats["derived_cost_per_kwh"] = round(total_cost / total_kwh, 4)
            cost_stats["note"] = (
                "Derived exclusively from reported cost and consumption in this dataset."
            )
        else:
            cost_stats["note"] = "Total consumption is zero; cost per kWh cannot be derived."

    # Baseline comparison
    baseline_kwh, method_used, dev_pct, baseline_note = calculate_baseline(
        df=df,
        method=baseline_method,
        target_kwh=target_kwh,
        group_by=group_by,
    )
    baseline_comp = {
        "baseline_method_used": method_used,
        "baseline_kwh": baseline_kwh,
        "total_actual_kwh": total_kwh,
        "overall_deviation_pct": dev_pct,
        "baseline_status": baseline_note,
    }

    # Group breakdowns
    breakdown_building: dict[str, float] | None = None
    if "building" in df.columns and df["building"].notna().any():
        b_sum = df.groupby("building")["energy_kwh"].sum().round(2).to_dict()
        breakdown_building = {str(k): float(v) for k, v in b_sum.items()}

    breakdown_dept: dict[str, float] | None = None
    if "department" in df.columns and df["department"].notna().any():
        d_sum = df.groupby("department")["energy_kwh"].sum().round(2).to_dict()
        breakdown_dept = {str(k): float(v) for k, v in d_sum.items()}

    breakdown_equip: dict[str, float] | None = None
    if "equipment" in df.columns and df["equipment"].notna().any():
        e_sum = df.groupby("equipment")["energy_kwh"].sum().round(2).to_dict()
        breakdown_equip = {str(k): float(v) for k, v in e_sum.items()}

    # Periodic summaries (monthly/weekly)
    periodic_summary: dict[str, Any] = {}
    if "date" in df.columns and pd.api.types.is_datetime64_any_dtype(df["date"]):
        # Monthly aggregation
        try:
            monthly = (
                df.set_index("date").resample("ME")["energy_kwh"].agg(["sum", "mean", "count"])
            )
            if not monthly.empty:
                periodic_summary["monthly"] = [
                    {
                        "period": idx.strftime("%Y-%m"),
                        "total_kwh": round(float(row["sum"]), 2),
                        "mean_kwh": round(float(row["mean"]), 2),
                        "records": int(row["count"]),
                    }
                    for idx, row in monthly.iterrows()
                    if row["count"] > 0
                ]
        except Exception:
            pass

    # Robust Outlier Detection for high consumption records
    z_scores, med_val, _scale_val = compute_robust_z_scores(df["energy_kwh"])
    high_records: list[dict[str, Any]] = []

    # Flag records where robust z-score > 2.0 (unusually high consumption)
    high_mask = z_scores > 2.0
    if high_mask.any():
        high_df = df[high_mask].copy()
        high_df["z_score"] = z_scores[high_mask]
        # Sort descending by z_score
        high_df = high_df.sort_values(by="z_score", ascending=False).head(20)

        for _, row in high_df.iterrows():
            act = float(row["energy_kwh"])
            record_dev_pct = (
                round(((act - med_val) / med_val) * 100.0, 2) if abs(med_val) > 1e-6 else None
            )
            dt_str = (
                row["date"].strftime("%Y-%m-%d")
                if hasattr(row["date"], "strftime")
                else str(row["date"])
            )
            high_records.append(
                {
                    "row_id": int(row.get("row_id", 0)),
                    "date": dt_str,
                    "energy_kwh": round(act, 2),
                    "building": str(row["building"]) if pd.notna(row.get("building")) else None,
                    "department": str(row["department"])
                    if pd.notna(row.get("department"))
                    else None,
                    "equipment": str(row["equipment"]) if pd.notna(row.get("equipment")) else None,
                    "deviation_score": round(float(row["z_score"]), 2),
                    "baseline_value": round(med_val, 2),
                    "deviation_pct": record_dev_pct,
                }
            )

    return {
        "statistics": stats,
        "cost_statistics": cost_stats,
        "baseline_comparison": baseline_comp,
        "breakdown_by_building": breakdown_building,
        "breakdown_by_department": breakdown_dept,
        "breakdown_by_equipment": breakdown_equip,
        "periodic_summary": periodic_summary,
        "high_consumption_records": high_records,
        "data_quality_summary": quality_summary or {},
    }
