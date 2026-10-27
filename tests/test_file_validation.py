"""Tests for file validation, path traversal defense, magic byte checking, and zip-bomb rejection."""

from pathlib import Path

import pytest

from app.core.errors import BadRequestError, UnsupportedMediaTypeError
from app.utils.file_validation import (
    detect_and_validate_file_type,
    sanitize_display_filename,
)
from tests.data_factory import (
    generate_macro_xlsm_bytes,
    generate_synthetic_csv_bytes,
    generate_synthetic_pdf_with_table_bytes,
    generate_synthetic_xls_bytes,
    generate_synthetic_xlsx_bytes,
    generate_zip_bomb_xlsx_bytes,
)


def test_sanitize_display_filename_path_traversal():
    # Unix and Windows path traversal attempts
    assert sanitize_display_filename("../../etc/passwd.csv") == "passwd.csv"
    assert sanitize_display_filename("..\\..\\Windows\\System32\\calc.csv") == "calc.csv"
    assert sanitize_display_filename("/root/secret.xlsx") == "secret.xlsx"
    assert sanitize_display_filename("C:\\Users\\admin\\desktop\\data.csv") == "data.csv"
    assert sanitize_display_filename(".hidden.csv") == "hidden.csv"
    assert sanitize_display_filename(None) == "uploaded_file"


def test_validate_valid_csv(tmp_path: Path):
    csv_file = tmp_path / "valid.csv"
    csv_file.write_bytes(generate_synthetic_csv_bytes())
    ft = detect_and_validate_file_type(csv_file, "valid.csv")
    assert ft == "csv"


def test_validate_valid_xlsx(tmp_path: Path):
    xlsx_file = tmp_path / "valid.xlsx"
    xlsx_file.write_bytes(generate_synthetic_xlsx_bytes())
    ft = detect_and_validate_file_type(xlsx_file, "valid.xlsx")
    assert ft == "xlsx"


def test_validate_valid_xls(tmp_path: Path):
    xls_file = tmp_path / "valid.xls"
    xls_file.write_bytes(generate_synthetic_xls_bytes())
    ft = detect_and_validate_file_type(xls_file, "valid.xls")
    assert ft == "xls"


def test_validate_valid_pdf(tmp_path: Path):
    pdf_file = tmp_path / "valid.pdf"
    pdf_file.write_bytes(generate_synthetic_pdf_with_table_bytes())
    ft = detect_and_validate_file_type(pdf_file, "valid.pdf")
    assert ft == "pdf"


def test_reject_empty_file(tmp_path: Path):
    empty_file = tmp_path / "empty.csv"
    empty_file.write_bytes(b"")
    with pytest.raises(BadRequestError, match="empty"):
        detect_and_validate_file_type(empty_file, "empty.csv")


def test_reject_wrong_extension_content_mismatch(tmp_path: Path):
    # .csv extension containing ZIP / binary data
    fake_csv = tmp_path / "fake.csv"
    fake_csv.write_bytes(b"PK\x03\x04ThisIsActuallyAZipFile")
    # CSV validator checks for binary or NUL bytes
    with pytest.raises((BadRequestError, UnsupportedMediaTypeError)):
        detect_and_validate_file_type(fake_csv, "fake.csv")


def test_reject_zip_bomb(tmp_path: Path):
    bomb_file = tmp_path / "bomb.xlsx"
    bomb_file.write_bytes(generate_zip_bomb_xlsx_bytes())
    with pytest.raises(BadRequestError, match="zip bomb"):
        detect_and_validate_file_type(bomb_file, "bomb.xlsx")


def test_reject_macro_xlsm(tmp_path: Path):
    macro_file = tmp_path / "macro.xlsx"
    macro_file.write_bytes(generate_macro_xlsm_bytes())
    with pytest.raises(BadRequestError, match="Macro-enabled"):
        detect_and_validate_file_type(macro_file, "macro.xlsx")
