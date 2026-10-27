"""Additional tests to maximize test coverage across preprocessing, extraction, and validation."""

from pathlib import Path

import pandas as pd
import pytest

from app.core.errors import BadRequestError
from app.database.connection import reset_database
from app.services.data_extraction import extract_xlsx
from app.services.preprocessing import (
    infer_granularity,
    map_columns,
    normalize_col_name,
    parse_numeric,
    preprocess_energy_data,
)
from tests.data_factory import (
    generate_synthetic_xlsx_bytes,
)


def test_preprocessing_units_and_granularity():
    # 1. Test column normalization
    assert normalize_col_name(" Total Energy (kWh) ") == "total_energy_kwh"
    assert normalize_col_name("Air Temp [°C]") == "air_temp_c"

    # 2. Test numeric parsing
    assert parse_numeric("$1,234.56") == 1234.56
    assert parse_numeric("1.234,56 €") == 1234.56
    assert parse_numeric("50.5 kWh") == 50.5
    assert parse_numeric("invalid") is None
    assert parse_numeric(None) is None

    # 3. Test granularity inference
    hourly_dates = pd.date_range("2024-01-01", periods=10, freq="h").to_pydatetime().tolist()
    assert infer_granularity(hourly_dates) == "hourly"

    weekly_dates = pd.date_range("2024-01-01", periods=10, freq="W").to_pydatetime().tolist()
    assert infer_granularity(weekly_dates) == "weekly"

    monthly_dates = pd.date_range("2024-01-01", periods=10, freq="ME").to_pydatetime().tolist()
    assert infer_granularity(monthly_dates) == "monthly"

    assert infer_granularity([]) == "irregular"


def test_preprocessing_mwh_and_extreme_temps():
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02"],
            "energy_consumed": [1.5, 2.0],  # In MWh
            "temp": [-60.0, 85.0],  # Extreme temperatures
            "hours": [28.0, -5.0],  # Out of range hours
        }
    )

    records, col_info, quality, warnings = preprocess_energy_data(
        raw_df=df,
        energy_unit="MWh",
    )

    assert len(records) == 2
    # 1.5 MWh -> 1500 kWh
    assert records[0]["energy_kwh"] == 1500.0
    assert any("MWh to kWh" in w for w in warnings)

    # Clamping hours
    assert records[0]["operating_hours"] == 24.0
    assert records[1]["operating_hours"] == 0.0

    # Extreme temp warning
    assert any("extreme temperature" in w.lower() for w in warnings)


def test_preprocessing_conflicting_column_mapping():
    # Two columns matching energy_kwh
    df = pd.DataFrame(
        {
            "date": ["2024-01-01"],
            "energy_kwh": [100.0],
            "kwh": [100.0],
        }
    )

    mapped, unmapped, warnings = map_columns(list(df.columns))
    assert "energy_kwh" in mapped
    assert "kwh" in unmapped
    assert any("already mapped" in w for w in warnings)


def test_extract_xlsx_multi_sheet(tmp_path: Path):
    xlsx_bytes = generate_synthetic_xlsx_bytes(multi_sheet=True)
    xlsx_file = tmp_path / "multi.xlsx"
    xlsx_file.write_bytes(xlsx_bytes)

    # Extract default sheet
    df1, w1, sheets1 = extract_xlsx(xlsx_file)
    assert len(df1) > 0
    assert "Summary" in sheets1

    # Extract explicit sheet
    df2, w2, sheets2 = extract_xlsx(xlsx_file, sheet_name="Summary")
    assert "Metric" in df2.columns

    # Unknown sheet -> BadRequestError
    with pytest.raises(BadRequestError, match="not found"):
        extract_xlsx(xlsx_file, sheet_name="NonExistentSheet")


def test_database_reset_confirmation(tmp_path: Path):
    test_db = tmp_path / "temp_reset.db"

    # Reset without confirmation must raise ValueError
    with pytest.raises(ValueError, match="confirmation"):
        reset_database(confirmed=False, db_path=str(test_db))

    # Reset with confirmation succeeds
    assert reset_database(confirmed=True, db_path=str(test_db)) is True
