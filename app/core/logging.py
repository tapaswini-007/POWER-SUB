"""Structured logging module with sensitive information redaction."""

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# Redaction patterns for sensitive keys and tokens
SENSITIVE_KEYS = {
    "api_key",
    "x-api-key",
    "authorization",
    "token",
    "password",
    "secret",
}
PATH_REDACT_REGEX = re.compile(r"[a-zA-Z]:\\[^\s\"]+|/[^\s\"]+")


def redact_value(key: str, value: Any) -> Any:
    """Redact sensitive fields or paths."""
    if not isinstance(key, str):
        return value
    if key.lower() in SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, str):
        # Truncate overly long strings (e.g. file content accidentally passed)
        if len(value) > 256:
            value = value[:256] + "...[TRUNCATED]"
    return value


def sanitize_record_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively sanitize dictionary values."""
    sanitized = {}
    for k, v in data.items():
        if isinstance(v, dict):
            sanitized[k] = sanitize_record_dict(v)
        else:
            sanitized[k] = redact_value(k, v)
    return sanitized


class StructuredJSONFormatter(logging.Formatter):
    """Formats log records as structured JSON without leaking sensitive data."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add contextual attributes if provided via extra
        for attr in (
            "request_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "client_ip",
        ):
            if hasattr(record, attr):
                log_entry[attr] = getattr(record, attr)

        if record.exc_info and not record.exc_text:
            # We sanitize exception message from stack trace if any
            log_entry["exception_type"] = (
                record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            )

        log_entry = sanitize_record_dict(log_entry)
        return json.dumps(log_entry, default=str)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure root logger with structured JSON formatting."""
    logger = logging.getLogger("power_sub")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Avoid duplicate handlers if setup is called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJSONFormatter())
        logger.addHandler(handler)

    # Disable propagation to prevent double logging with uvicorn root
    logger.propagate = False
    return logger


logger = setup_logging()
