"""Tests for CSV Formula Injection neutralization."""

import pandas as pd

from app.utils.csv_safety import (
    sanitize_csv_cell,
    sanitize_dataframe_for_csv,
    sanitize_row_for_csv,
)


def test_sanitize_csv_cell_dangerous_formulas():
    # Leading =
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("=cmd|'/C calc'!A0") == "'=cmd|'/C calc'!A0"

    # Leading @
    assert sanitize_csv_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)"

    # Leading Tab and Carriage Return
    assert sanitize_csv_cell("\tmalicious") == "'\tmalicious"
    assert sanitize_csv_cell("\rmalicious") == "'\rmalicious"


def test_sanitize_csv_cell_legitimate_numbers():
    # Legitimate numbers should NOT be prefixed with quote
    assert sanitize_csv_cell(-12.5) == -12.5
    assert sanitize_csv_cell("-12.5") == "-12.5"
    assert sanitize_csv_cell("+100") == "+100"
    assert sanitize_csv_cell(0) == 0
    assert sanitize_csv_cell(45.67) == 45.67


def test_sanitize_csv_cell_dangerous_plus_minus():
    # Text starting with + or - that is NOT a number must be neutralized
    assert sanitize_csv_cell("-cmd|'/C calc'") == "'-cmd|'/C calc'"
    assert sanitize_csv_cell("+cmd|'/C calc'") == "'+cmd|'/C calc'"
    assert sanitize_csv_cell("-2+3*4") == "'-2+3*4"


def test_sanitize_row_and_dataframe():
    row = {
        "building": "=BuildingA",
        "energy_kwh": 120.5,
        "note": "+alert",
        "delta": "-5.2",
    }
    sanitized_row = sanitize_row_for_csv(row)
    assert sanitized_row["building"] == "'=BuildingA"
    assert sanitized_row["energy_kwh"] == 120.5
    assert sanitized_row["note"] == "'+alert"
    assert sanitized_row["delta"] == "-5.2"

    df = pd.DataFrame([row])
    sanitized_df = sanitize_dataframe_for_csv(df)
    assert sanitized_df.loc[0, "building"] == "'=BuildingA"
    assert sanitized_df.loc[0, "note"] == "'+alert"
    assert sanitized_df.loc[0, "delta"] == "-5.2"
