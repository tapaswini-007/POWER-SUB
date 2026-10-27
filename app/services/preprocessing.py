"""Data preprocessing, column mapping, date parsing, sanitization, and data quality metrics."""

import re
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from dateutil import parser as date_parser

from app.core.errors import ValidationError

STANDARD_COLUMNS = [
    "date",
    "energy_kwh",
    "building",
    "department",
    "equipment",
    "cost",
    "temperature",
    "operating_hours",
]

ALIAS_MAPPING: dict[str, list[str]] = {
    "energy_kwh": [
        "energy_kwh",
        "kwh",
        "consumption",
        "energy",
        "usage",
        "energy_consumed",
        "power_kwh",
        "active_power",
        "total_kwh",
        "electricity_kwh",
        "power",
    ],
    "date": [
        "date",
        "timestamp",
        "datetime",
        "day",
        "reading_date",
        "time",
        "date_time",
        "period",
        "record_date",
    ],
    "building": [
        "building",
        "bldg",
        "site",
        "facility",
        "location",
        "premises",
        "property",
        "plant",
    ],
    "department": [
        "department",
        "dept",
        "division",
        "unit",
        "sector",
        "cost_center",
        "area",
    ],
    "equipment": [
        "equipment",
        "machine",
        "asset",
        "device",
        "appliance",
        "meter",
        "submeter",
        "load",
    ],
    "cost": [
        "cost",
        "total_cost",
        "cost_usd",
        "cost_eur",
        "expense",
        "amount",
        "electricity_cost",
        "bill_amount",
        "charges",
    ],
    "temperature": [
        "temperature",
        "temp",
        "outdoor_temp",
        "ambient_temp",
        "air_temp",
        "deg_c",
        "deg_f",
        "temperature_c",
    ],
    "operating_hours": [
        "operating_hours",
        "hours",
        "run_hours",
        "op_hours",
        "runtime",
        "active_hours",
        "working_hours",
        "operating_time",
    ],
}


def normalize_col_name(col: str) -> str:
    """Normalize a column name: strip, lowercase, remove punctuation, collapse underscores."""
    col = str(col).strip().lower()
    col = re.sub(r"[\(\)\[\]\{\}\<\>\/\\:\,\.\;\%\$\£\€\*\#]", " ", col)
    col = re.sub(r"[-\s]+", "_", col).strip("_")
    return col


def map_columns(raw_columns: list[str]) -> tuple[dict[str, str], list[str], list[str]]:
    """Map raw column headers to standard columns using the alias table."""
    mapped: dict[str, str] = {}  # raw_col -> standard_col
    unmapped: list[str] = []
    warnings: list[str] = []
    standard_claimed: dict[str, str] = {}  # standard_col -> first_raw_col

    for raw in raw_columns:
        norm = normalize_col_name(raw)
        matched_standard = None

        for std_col, aliases in ALIAS_MAPPING.items():
            if norm == std_col or norm in aliases:
                matched_standard = std_col
                break

        # If not matched directly, check substring matching
        if not matched_standard:
            for std_col, aliases in ALIAS_MAPPING.items():
                for alias in aliases:
                    if alias in norm or norm in alias:
                        matched_standard = std_col
                        break
                if matched_standard:
                    break

        if matched_standard:
            if matched_standard in standard_claimed:
                existing = standard_claimed[matched_standard]
                warnings.append(
                    f"Column '{raw}' also matches standard column '{matched_standard}' "
                    f"(already mapped to '{existing}'). Skipping '{raw}'."
                )
                unmapped.append(raw)
            else:
                mapped[raw] = matched_standard
                standard_claimed[matched_standard] = raw
        else:
            unmapped.append(raw)

    return mapped, unmapped, warnings


def parse_numeric(val: Any) -> float | None:
    """Parse numeric values with currency symbols, thousand separators, and decimal commas."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val) if not np.isnan(val) else None

    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null", "n/a", "-", "--"):
        return None

    # Remove currency symbols and units
    s = re.sub(r"[\$\€\£\₹\¥\%\s]", "", s)
    s = re.sub(r"(kwh|wh|mwh|kw|w|degc|c|f)$", "", s, flags=re.IGNORECASE).strip()

    # Handle thousands and decimal separator variations
    if "," in s and "." in s:
        # Standard: 1,234.56 vs European: 1.234,56
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        # Check if single comma is decimal or thousands
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")

    try:
        f = float(s)
        return f if not np.isnan(f) else None
    except ValueError:
        return None


def parse_date_value(val: Any, date_format_hint: str | None = None) -> tuple[datetime | None, bool]:
    """Parse date or timestamp string into datetime, flagging ambiguity."""
    if val is None or pd.isna(val):
        return None, False

    if isinstance(val, (datetime, pd.Timestamp)):
        return val.to_pydatetime() if hasattr(val, "to_pydatetime") else val, False

    s = str(val).strip()
    if not s:
        return None, False

    is_ambiguous = False

    # If hint provided, try that first
    if date_format_hint:
        try:
            return datetime.strptime(s, date_format_hint), False
        except ValueError:
            pass

    # Try ISO format
    try:
        return datetime.fromisoformat(s), False
    except ValueError:
        pass

    # Check for potential day/month ambiguity in numeric dates like 03/04/2024
    ambiguous_match = re.match(r"^(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})", s)
    if ambiguous_match:
        p1, p2 = int(ambiguous_match.group(1)), int(ambiguous_match.group(2))
        if p1 <= 12 and p2 <= 12 and p1 != p2:
            is_ambiguous = True

    try:
        dt = date_parser.parse(s, fuzzy=False)
        return dt, is_ambiguous
    except Exception:
        pass

    return None, False


def infer_granularity(dates: list[datetime]) -> str:
    """Infer time granularity from sorted distinct datetimes."""
    if len(dates) < 2:
        return "irregular"

    sorted_dates = sorted(dates)
    diffs = [
        (sorted_dates[i] - sorted_dates[i - 1]).total_seconds()
        for i in range(1, min(len(sorted_dates), 100))
    ]
    median_diff = float(np.median(diffs))

    if 3500 <= median_diff <= 3700:
        return "hourly"
    elif 82800 <= median_diff <= 90000:
        return "daily"
    elif 590000 <= median_diff <= 620000:
        return "weekly"
    elif 2300000 <= median_diff <= 2800000:
        return "monthly"
    return "irregular"


def preprocess_energy_data(
    raw_df: pd.DataFrame,
    sheet_name: str | None = None,
    date_format_hint: str | None = None,
    energy_unit: str = "kWh",
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], list[str]]:
    """Clean, standardize, validate, and extract quality metrics from raw tabular data.

    Returns:
        (cleaned_records, column_info, data_quality_summary, warnings)
    """
    total_input_rows = len(raw_df)
    warnings: list[str] = []
    rejection_reasons: dict[str, int] = {}
    correction_reasons: dict[str, int] = {}
    example_rejections: list[dict[str, Any]] = []

    # 1. Map columns
    mapped_cols, unmapped_cols, map_warnings = map_columns(list(raw_df.columns))
    warnings.extend(map_warnings)

    column_info = {
        "detected": list(raw_df.columns),
        "mapped": mapped_cols,
        "unmapped": unmapped_cols,
    }

    # Verify required columns: energy_kwh and date
    mapped_standards = set(mapped_cols.values())
    if "energy_kwh" not in mapped_standards:
        raise ValidationError(
            f"No recognizable energy consumption column found. "
            f"Expected one of: {', '.join(ALIAS_MAPPING['energy_kwh'])}."
        )
    if "date" not in mapped_standards:
        raise ValidationError(
            f"No recognizable date/timestamp column found. "
            f"Expected one of: {', '.join(ALIAS_MAPPING['date'])}."
        )

    # Rename mapped columns to standard names
    df = raw_df.rename(columns=mapped_cols).copy()

    # Ensure all standard columns exist in DataFrame with None defaults
    for col in STANDARD_COLUMNS:
        if col not in df.columns:
            df[col] = None

    # Handle energy unit conversions
    unit_multiplier = 1.0
    unit_norm = (energy_unit or "kWh").strip().lower()
    if unit_norm == "wh":
        unit_multiplier = 0.001
        warnings.append("Converted energy values from Wh to kWh (divided by 1,000).")
    elif unit_norm == "mwh":
        unit_multiplier = 1000.0
        warnings.append("Converted energy values from MWh to kWh (multiplied by 1,000).")
    elif unit_norm != "kwh":
        warnings.append(f"Unrecognized energy unit '{energy_unit}', assuming kWh.")

    # 2. Check for exact duplicate rows
    exact_dups = df.duplicated()
    exact_dup_count = int(exact_dups.sum())
    if exact_dup_count > 0:
        df = df[~exact_dups].copy()
        correction_reasons["exact_duplicate_rows_dropped"] = exact_dup_count
        warnings.append(f"Dropped {exact_dup_count} exact duplicate rows.")

    accepted_records: list[dict[str, Any]] = []
    parsed_datetimes: list[datetime] = []
    has_date_ambiguity = False

    # 3. Clean and validate row-by-row
    for idx, row in df.iterrows():
        row_id = int(idx) + 1
        was_corrected = False

        # --- Date validation ---
        dt, ambiguous = parse_date_value(row["date"], date_format_hint)
        if ambiguous:
            has_date_ambiguity = True

        if dt is None:
            rejection_reasons["unparseable_or_missing_date"] = (
                rejection_reasons.get("unparseable_or_missing_date", 0) + 1
            )
            if len(example_rejections) < 5:
                example_rejections.append(
                    {"row_id": row_id, "reason": f"Unparseable date: '{row['date']}'"}
                )
            continue

        # --- Energy kWh validation ---
        energy_val = parse_numeric(row["energy_kwh"])
        if energy_val is None:
            rejection_reasons["invalid_numeric_energy"] = (
                rejection_reasons.get("invalid_numeric_energy", 0) + 1
            )
            if len(example_rejections) < 5:
                example_rejections.append(
                    {
                        "row_id": row_id,
                        "reason": f"Invalid numeric energy value: '{row['energy_kwh']}'",
                    }
                )
            continue

        # Reject negative energy consumption
        if energy_val < 0:
            rejection_reasons["negative_energy_consumption"] = (
                rejection_reasons.get("negative_energy_consumption", 0) + 1
            )
            if len(example_rejections) < 5:
                example_rejections.append(
                    {
                        "row_id": row_id,
                        "reason": f"Negative energy consumption: {energy_val} kWh",
                    }
                )
            continue

        final_energy = round(energy_val * unit_multiplier, 4)

        # --- Cost validation ---
        cost_val = parse_numeric(row["cost"])
        if row["cost"] is not None and cost_val is None:
            was_corrected = True
            correction_reasons["invalid_cost_coerced_to_null"] = (
                correction_reasons.get("invalid_cost_coerced_to_null", 0) + 1
            )

        # --- Temperature validation ---
        temp_val = parse_numeric(row["temperature"])
        if row["temperature"] is not None and temp_val is None:
            was_corrected = True
            correction_reasons["invalid_temperature_coerced_to_null"] = (
                correction_reasons.get("invalid_temperature_coerced_to_null", 0) + 1
            )
        elif temp_val is not None and (temp_val < -50 or temp_val > 70):
            # Flag extreme unrealistic temperatures
            warnings.append(
                f"Row {row_id} contains extreme temperature value ({temp_val}°C). Retained but flagged."
            )

        # --- Operating hours validation ---
        hours_val = parse_numeric(row["operating_hours"])
        if row["operating_hours"] is not None and hours_val is None:
            was_corrected = True
            correction_reasons["invalid_operating_hours_coerced_to_null"] = (
                correction_reasons.get("invalid_operating_hours_coerced_to_null", 0) + 1
            )
        elif hours_val is not None and (hours_val < 0 or hours_val > 24):
            # Clamping or reporting operating hours outside 0-24
            was_corrected = True
            correction_reasons["operating_hours_outside_0_24_clamped"] = (
                correction_reasons.get("operating_hours_outside_0_24_clamped", 0) + 1
            )
            hours_val = max(0.0, min(24.0, hours_val))

        # Text fields
        bldg = (
            str(row["building"]).strip()
            if row["building"] is not None
            and str(row["building"]).strip() != ""
            and str(row["building"]).lower() != "nan"
            else None
        )
        dept = (
            str(row["department"]).strip()
            if row["department"] is not None
            and str(row["department"]).strip() != ""
            and str(row["department"]).lower() != "nan"
            else None
        )
        equip = (
            str(row["equipment"]).strip()
            if row["equipment"] is not None
            and str(row["equipment"]).strip() != ""
            and str(row["equipment"]).lower() != "nan"
            else None
        )

        record = {
            "row_id": row_id,
            "date": dt.isoformat(),
            "energy_kwh": final_energy,
            "building": bldg,
            "department": dept,
            "equipment": equip,
            "cost": round(cost_val, 2) if cost_val is not None else None,
            "temperature": round(temp_val, 2) if temp_val is not None else None,
            "operating_hours": round(hours_val, 2) if hours_val is not None else None,
            "was_corrected": was_corrected,
        }

        accepted_records.append(record)
        parsed_datetimes.append(dt)

    if has_date_ambiguity and not date_format_hint:
        warnings.append(
            "Dates with day <= 12 and month <= 12 were detected (ambiguous day vs month). "
            "Consider specifying 'date_format_hint' (e.g. '%Y-%m-%d' or '%d/%m/%Y') if parsing looks inverted."
        )

    # 4. Check for duplicate keys: date + building + department + equipment
    key_tuples = [
        (r["date"], r["building"], r["department"], r["equipment"]) for r in accepted_records
    ]
    duplicate_keys_count = len(key_tuples) - len(set(key_tuples))
    if duplicate_keys_count > 0:
        warnings.append(
            f"Detected {duplicate_keys_count} records with conflicting/duplicate primary keys "
            f"(same date, building, department, and equipment). Records were retained with a warning."
        )

    # Calculate summary metrics
    accepted_rows = len(accepted_records)
    rejected_rows = sum(rejection_reasons.values())
    corrected_rows = sum(correction_reasons.values()) + sum(
        1 for r in accepted_records if r["was_corrected"]
    )

    if accepted_rows == 0:
        raise ValidationError(
            f"All {total_input_rows} input rows were rejected during validation. "
            f"Reasons: {rejection_reasons}"
        )

    # Missing values per standard column in accepted records
    missing_values = {
        col: sum(1 for r in accepted_records if r.get(col) is None) for col in STANDARD_COLUMNS
    }

    granularity = infer_granularity(parsed_datetimes)

    data_quality_summary = {
        "total_input_rows": total_input_rows,
        "accepted_rows": accepted_rows,
        "corrected_rows": corrected_rows,
        "rejected_rows": rejected_rows,
        "rejection_reasons": rejection_reasons,
        "correction_reasons": correction_reasons,
        "example_rejections": example_rejections,
        "granularity": granularity,
        "missing_values_per_column": missing_values,
    }

    return accepted_records, column_info, data_quality_summary, warnings
