"""File upload streaming, size enforcement, and deep signature validation."""

import os
import re
import uuid
import zipfile
from pathlib import Path

import pymupdf
from fastapi import UploadFile

from app.core.config import settings
from app.core.errors import (
    BadRequestError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"
OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".pdf"}


def sanitize_display_filename(filename: str | None) -> str:
    """Sanitize original client filename for safe display metadata."""
    if not filename:
        return "uploaded_file"

    # Strip directory path components (both unix and windows)
    clean_name = os.path.basename(filename).replace("\\", "/")
    clean_name = clean_name.split("/")[-1]

    # Remove non-printable / control characters
    clean_name = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", clean_name).strip()

    # Disallow leading dots to prevent hidden file styling
    clean_name = clean_name.lstrip(".")

    if not clean_name:
        return "uploaded_file"

    # Cap length to 100 characters while preserving extension
    if len(clean_name) > 100:
        stem, ext = os.path.splitext(clean_name)
        clean_name = stem[: 100 - len(ext)] + ext

    return clean_name


async def stream_upload_to_temp_file(
    upload_file: UploadFile,
    max_mb: int = settings.MAX_UPLOAD_MB,
    temp_dir_str: str = settings.UPLOAD_TEMP_DIR,
) -> tuple[Path, str]:
    """Stream an uploaded file to a uniquely named temp file on disk.

    Enforces size limits during streaming to prevent RAM exhaustion.
    Guarantees the destination path remains within the dedicated temp directory.
    """
    max_bytes = max_mb * 1024 * 1024
    temp_dir = Path(temp_dir_str).resolve()
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Check Content-Length header if provided
    content_length = upload_file.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise PayloadTooLargeError(f"Uploaded file exceeds maximum limit of {max_mb} MB.")
        except ValueError:
            pass

    # 2. Generate random server-side filename
    unique_name = f"upload_{uuid.uuid4().hex}.tmp"
    dest_path = (temp_dir / unique_name).resolve()

    # Security check: verify destination stays within temp directory
    try:
        if not dest_path.is_relative_to(temp_dir):
            raise BadRequestError("Invalid file path resolution.")
    except AttributeError:
        # Fallback for Python < 3.9 compatibility
        if not str(dest_path).startswith(str(temp_dir)):
            raise BadRequestError("Invalid file path resolution.")

    # 3. Stream in chunks of 64 KB
    total_bytes = 0
    chunk_size = 64 * 1024

    try:
        with open(dest_path, "wb") as out_f:
            while True:
                chunk = await upload_file.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise PayloadTooLargeError(
                        f"Uploaded file exceeds maximum limit of {max_mb} MB."
                    )
                out_f.write(chunk)
    except Exception:
        # Clean up partial file on failure
        if dest_path.exists():
            try:
                dest_path.unlink()
            except OSError:
                pass
        raise

    if total_bytes == 0:
        if dest_path.exists():
            dest_path.unlink()
        raise BadRequestError("Uploaded file is empty (0 bytes).")

    sanitized_filename = sanitize_display_filename(upload_file.filename)
    return dest_path, sanitized_filename


def detect_and_validate_file_type(file_path: Path, filename_hint: str) -> str:
    """Validate file content by checking magic bytes and format-specific structures.

    Returns the canonical type: 'csv', 'xlsx', 'xls', or 'pdf'.
    Raises 400, 413, or 415 if validation fails.
    """
    if not file_path.exists():
        raise BadRequestError("Upload temporary file was not found.")

    file_size = file_path.stat().st_size
    if file_size == 0:
        raise BadRequestError("Uploaded file is empty.")

    ext = Path(filename_hint).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedMediaTypeError(
            f"Unsupported file extension '{ext}'. Supported formats: .csv, .xlsx, .xls, .pdf"
        )

    # Read first 8 KB for magic bytes inspection
    with open(file_path, "rb") as f:
        header = f.read(8192)

    # 1. PDF Validation
    if header.startswith(PDF_MAGIC):
        try:
            doc = pymupdf.open(str(file_path))
            if doc.is_encrypted:
                doc.close()
                raise BadRequestError(
                    "Encrypted or password-protected PDF files are not supported."
                )
            if doc.page_count > settings.MAX_PDF_PAGES:
                page_cnt = doc.page_count
                doc.close()
                raise BadRequestError(
                    f"PDF page count ({page_cnt}) exceeds limit of {settings.MAX_PDF_PAGES} pages."
                )
            doc.close()
            return "pdf"
        except Exception as e:
            if isinstance(e, BadRequestError):
                raise
            raise BadRequestError(f"Corrupted or invalid PDF file: {e!s}")

    # 2. XLSX (OpenXML ZIP archive) Validation
    if header.startswith(ZIP_MAGIC):
        try:
            if not zipfile.is_zipfile(file_path):
                raise BadRequestError("Corrupted Excel archive.")

            with zipfile.ZipFile(file_path, "r") as z:
                names = z.namelist()

                # Must contain core workbook structures
                if "[Content_Types].xml" not in names or not any(
                    n.startswith("xl/") for n in names
                ):
                    raise BadRequestError("ZIP archive is not a valid Excel (.xlsx) workbook.")

                # Reject macro-enabled workbooks
                if any("vbaProject.bin" in n or n.endswith(".vba") for n in names):
                    raise BadRequestError(
                        "Macro-enabled Excel workbooks (.xlsm / VBA) are prohibited for security."
                    )

                # Zip bomb / decompression guard
                max_uncompressed = settings.MAX_XLSX_UNCOMPRESSED_MB * 1024 * 1024
                total_uncompressed = sum(info.file_size for info in z.infolist())
                if total_uncompressed > max_uncompressed:
                    raise PayloadTooLargeError(
                        f"Excel uncompressed size ({total_uncompressed // (1024 * 1024)} MB) "
                        f"exceeds limit of {settings.MAX_XLSX_UNCOMPRESSED_MB} MB."
                    )

                # Compression ratio check for zip bomb protection
                if file_size > 0:
                    ratio = total_uncompressed / file_size
                    if ratio > 50 and total_uncompressed > (10 * 1024 * 1024):
                        raise BadRequestError(
                            "Suspicious Excel compression ratio detected (potential zip bomb)."
                        )

            return "xlsx"
        except Exception as e:
            if isinstance(e, (BadRequestError, PayloadTooLargeError)):
                raise
            raise BadRequestError(f"Corrupted or invalid Excel file: {e!s}")

    # 3. XLS (Legacy Excel OLE2) Validation
    if header.startswith(OLE2_MAGIC):
        return "xls"

    # 4. CSV Validation
    # If file does not start with binary magic, check for plain text
    if ext == ".csv":
        # Check for NUL bytes (proves binary file)
        if b"\x00" in header:
            raise BadRequestError("Binary data or NUL bytes detected in CSV file.")

        # Try common text decodings
        decoded_text = None
        for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
            try:
                decoded_text = header.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if decoded_text is None:
            raise BadRequestError("Unable to decode CSV text with supported encodings.")

        # Ensure it has readable text
        if not decoded_text.strip():
            raise BadRequestError("CSV file contains no readable text.")

        return "csv"

    # Extension was declared as something else or header didn't match extension
    raise UnsupportedMediaTypeError(
        f"File content does not match allowed signatures. Declared: {ext}."
    )
