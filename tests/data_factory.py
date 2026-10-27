"""Synthetic test data generator for unit and integration testing.

ALL DATA GENERATED HERE IS STRICTLY SYNTHETIC TEST DATA FOR CODE VERIFICATION,
NOT REAL-WORLD ENERGY MEASUREMENTS.
"""

import io
import zipfile
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pymupdf
import xlwt


def generate_synthetic_energy_df(
    days: int = 90,
    buildings: list | None = None,
    seed: int = 42,
    include_outliers: bool = True,
    include_missing: bool = True,
    include_duplicate: bool = True,
) -> pd.DataFrame:
    """Generate a realistic synthetic energy DataFrame labeled SYNTHETIC TEST DATA."""
    np.random.seed(seed)
    buildings = buildings or ["Building_A", "Building_B"]
    base_date = datetime(2024, 1, 1)

    rows = []
    for b in buildings:
        base_kwh = 120.0 if b == "Building_A" else 85.0
        for day_offset in range(days):
            current_date = base_date + timedelta(days=day_offset)
            weekday = current_date.weekday()

            # Weekday vs Weekend pattern
            day_factor = 0.55 if weekday >= 5 else 1.0

            # Temperature variation
            temp = round(15.0 + 8.0 * np.sin(day_offset / 15.0) + np.random.normal(0, 2.0), 1)

            # Operating hours
            op_hours = 0.0 if weekday >= 5 else round(float(np.random.choice([8.0, 9.0, 10.0])), 1)

            # Base energy with noise
            noise = np.random.normal(0, 5.0)
            energy = round(max(10.0, (base_kwh * day_factor) + (abs(temp - 20.0) * 1.5) + noise), 2)

            cost = round(energy * 0.15, 2)

            rows.append(
                {
                    "date": current_date.strftime("%Y-%m-%d"),
                    "building": b,
                    "department": "Operations",
                    "equipment": "HVAC_Main",
                    "energy_kwh": energy,
                    "cost": cost,
                    "temperature": temp,
                    "operating_hours": op_hours,
                }
            )

    df = pd.DataFrame(rows)

    # 1. Injected outliers for anomaly testing
    if include_outliers and len(df) > 10:
        # Inject deliberate high-consumption spike on row 15
        df.loc[15, "energy_kwh"] = 450.0
        # Inject weekend running when op_hours is 0
        df.loc[25, "energy_kwh"] = 280.0
        df.loc[25, "operating_hours"] = 0.0

    # 2. Inject one missing value
    if include_missing and len(df) > 20:
        df.loc[20, "cost"] = np.nan

    # 3. Inject one duplicate row
    if include_duplicate and len(df) > 5:
        dup_row = df.iloc[[4]].copy()
        df = pd.concat([df, dup_row], ignore_index=True)

    return df


def generate_synthetic_csv_bytes(
    df: pd.DataFrame | None = None,
    encoding: str = "utf-8",
) -> bytes:
    """Export DataFrame as CSV bytes labeled SYNTHETIC."""
    if df is None:
        df = generate_synthetic_energy_df()
    csv_str = df.to_csv(index=False)
    return csv_str.encode(encoding)


def generate_synthetic_xlsx_bytes(
    df: pd.DataFrame | None = None,
    sheet_name: str = "EnergyData",
    multi_sheet: bool = False,
) -> bytes:
    """Generate Excel (.xlsx) file in-memory."""
    if df is None:
        df = generate_synthetic_energy_df()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        if multi_sheet:
            summary_df = pd.DataFrame(
                {
                    "Metric": ["Total", "Count"],
                    "Value": [df["energy_kwh"].sum(), len(df)],
                }
            )
            summary_df.to_excel(writer, sheet_name="Summary", index=False)

    return output.getvalue()


def generate_synthetic_xls_bytes(df: pd.DataFrame | None = None) -> bytes:
    """Generate legacy Excel (.xls) bytes using xlwt."""
    if df is None:
        df = generate_synthetic_energy_df()

    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("EnergyRecords")

    # Header
    for c_idx, col in enumerate(df.columns):
        ws.write(0, c_idx, str(col))

    # Rows
    for r_idx, (_, row) in enumerate(df.iterrows(), start=1):
        for c_idx, col in enumerate(df.columns):
            val = row[col]
            if pd.isna(val):
                ws.write(r_idx, c_idx, "")
            elif isinstance(val, (int, float)):
                ws.write(r_idx, c_idx, float(val))
            else:
                ws.write(r_idx, c_idx, str(val))

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def generate_synthetic_pdf_with_table_bytes(df: pd.DataFrame | None = None) -> bytes:
    """Generate synthetic PDF containing a structured table using PyMuPDF."""
    if df is None:
        df = generate_synthetic_energy_df(days=10)

    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)  # Standard Letter

    # Title text
    page.insert_text((50, 40), "SYNTHETIC ENERGY REPORT - TABULAR DATA", fontsize=14)

    # Simple text table format
    header = list(df.columns)
    header_text = " | ".join(header)
    page.insert_text((50, 70), header_text, fontsize=8)

    y = 90
    for _, row in df.head(30).iterrows():
        row_str = " | ".join(str(row[c]) for c in header)
        page.insert_text((50, y), row_str, fontsize=7)
        y += 15

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_image_only_pdf_bytes() -> bytes:
    """Generate a PDF containing only an image drawing (no text layer) to test OCR rejection."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    # Draw shapes instead of text
    shape = page.new_shape()
    shape.draw_rect(pymupdf.Rect(100, 100, 400, 400))
    shape.finish(fill=(0.8, 0.8, 0.8), color=(0.2, 0.2, 0.2))
    shape.commit()

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_zip_bomb_xlsx_bytes() -> bytes:
    """Create a simulated zip bomb with high compression ratio."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", b"<Types/>")
        z.writestr("xl/workbook.xml", b"<workbook/>")
        # Write large block of zeros (highly compressible)
        z.writestr("xl/worksheets/sheet1.xml", b"0" * (12 * 1024 * 1024))
    return buf.getvalue()


def generate_macro_xlsm_bytes() -> bytes:
    """Create a mock Excel file with prohibited macro file vbaProject.bin."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", b"<Types/>")
        z.writestr("xl/workbook.xml", b"<workbook/>")
        z.writestr("xl/vbaProject.bin", b"DANGEROUS_VBA_MACRO_PAYLOAD")
    return buf.getvalue()
