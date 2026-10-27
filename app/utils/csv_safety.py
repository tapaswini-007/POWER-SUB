"""CSV Formula Injection (CSV Injection / Formula Injection) neutralization."""

from typing import Any

import pandas as pd

DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def is_numeric_string(s: str) -> bool:
    """Check if string is a standard integer or floating-point representation."""
    try:
        float(s.strip())
        return True
    except (ValueError, TypeError):
        return False


def sanitize_csv_cell(value: Any) -> Any:
    """Neutralize potential CSV formula injection in cell values.

    Prefixes dangerous leading characters with a single quote (') if the value
    is a string and not a legitimate numeric constant.
    """
    if value is None:
        return ""

    # Integers, floats, booleans are safe
    if isinstance(value, (int, float, bool)):
        return value

    if isinstance(value, str):
        if not value:
            return ""

        # Check dangerous leading character directly (tab, \r, =, +, -, @)
        # Also check after stripping leading spaces
        l_val = value.lstrip(" ")
        if not l_val:
            return value

        if l_val.startswith(DANGEROUS_PREFIXES):
            # If it starts with + or - but represents a valid number, keep as-is
            if l_val[0] in ("+", "-") and is_numeric_string(l_val):
                return value
            return f"'{value}"

    return value


def sanitize_row_for_csv(row: dict[str, Any]) -> dict[str, Any]:
    """Sanitize all string values in a single dictionary row."""
    return {k: sanitize_csv_cell(v) for k, v in row.items()}


def sanitize_dataframe_for_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Apply formula injection neutralization across all string/object columns in a DataFrame."""
    clean_df = df.copy()
    for col in clean_df.columns:
        if clean_df[col].dtype == object or pd.api.types.is_string_dtype(clean_df[col]):
            clean_df[col] = clean_df[col].apply(sanitize_csv_cell)
    return clean_df
