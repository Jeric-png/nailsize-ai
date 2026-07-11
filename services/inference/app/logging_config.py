import json
import logging
import sys
from typing import Any, TextIO

ALLOWED_LOG_FIELDS = {
    "event",
    "request_id",
    "encoded_bytes",
    "width_px",
    "height_px",
    "processing_ms",
    "duration_ms",
    "stage",
    "cold_start",
    "ready",
    "model_version",
    "chart_version",
    "confidence_bucket",
    "status_code",
    "error_code",
}


def configure_json_logger(name: str, level: str, *, stream: TextIO | None = None) -> logging.Logger:
    """Create a JSON-only logger that Cloud Logging can parse as jsonPayload."""
    resolved_level = logging.getLevelName(level.upper())
    if not isinstance(resolved_level, int):
        raise ValueError(f"Unsupported log level: {level}")

    logger = logging.getLogger(name)
    logger.setLevel(resolved_level)
    logger.handlers.clear()
    handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def safe_log(logger: logging.Logger, level: int, **fields: Any) -> None:
    unsafe = set(fields) - ALLOWED_LOG_FIELDS
    if unsafe:
        raise ValueError(f"Unsafe log fields: {sorted(unsafe)}")
    payload = {"severity": logging.getLevelName(level), **fields}
    logger.log(level, json.dumps(payload, separators=(",", ":"), sort_keys=True))
