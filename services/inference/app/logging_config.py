import json
import logging
from typing import Any

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


def safe_log(logger: logging.Logger, level: int, **fields: Any) -> None:
    unsafe = set(fields) - ALLOWED_LOG_FIELDS
    if unsafe:
        raise ValueError(f"Unsafe log fields: {sorted(unsafe)}")
    logger.log(level, json.dumps(fields, separators=(",", ":"), sort_keys=True))
