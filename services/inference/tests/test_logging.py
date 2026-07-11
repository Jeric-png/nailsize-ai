import io
import json
import logging
from uuid import UUID

import pytest
from test_api import jpeg_fixture, post_image

from app.logging_config import configure_json_logger, safe_log


class RecordCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def collect_inference_records() -> tuple[logging.Logger, RecordCollector]:
    logger = logging.getLogger("nailsize.inference")
    collector = RecordCollector()
    logger.addHandler(collector)
    return logger, collector


@pytest.mark.parametrize(
    "field",
    ["filename", "image", "contour", "projected_width_mm", "recommended_size", "result_summary"],
)
def test_sensitive_log_fields_are_rejected(field: str) -> None:
    with pytest.raises(ValueError, match="Unsafe log fields"):
        safe_log(logging.getLogger("test"), logging.INFO, event="test", **{field: "secret"})


def test_measurement_logs_safe_stage_and_request_metrics() -> None:
    logger, collector = collect_inference_records()
    try:
        response = post_image(jpeg_fixture(with_reference=True))
    finally:
        logger.removeHandler(collector)

    records = [json.loads(record.message) for record in collector.records]
    stages = {record.get("stage") for record in records if record["event"] == "stage_completed"}
    completed = next(record for record in records if record["event"] == "request_completed")

    assert stages == {"upload_decode", "capture_quality"}
    assert completed["status_code"] == 200
    assert completed["processing_ms"] >= 0
    assert response.headers["x-request-id"] == completed["request_id"]
    UUID(completed["request_id"])


def test_server_request_id_does_not_reflect_untrusted_header() -> None:
    logger, collector = collect_inference_records()
    try:
        response = post_image(
            jpeg_fixture(), headers={"X-Request-ID": "private-customer-identifier"}
        )
    finally:
        logger.removeHandler(collector)

    assert response.headers["x-request-id"] != "private-customer-identifier"
    assert "private-customer-identifier" not in "".join(
        record.message for record in collector.records
    )


def test_json_logger_emits_cloud_logging_compatible_json_only() -> None:
    stream = io.StringIO()
    logger = configure_json_logger("test.cloud-logging", "INFO", stream=stream)

    safe_log(logger, logging.WARNING, event="request_failed", status_code=500)

    payload = json.loads(stream.getvalue())
    assert payload == {
        "event": "request_failed",
        "severity": "WARNING",
        "status_code": 500,
    }
    assert logger.propagate is False


def test_json_logger_rejects_unknown_log_level() -> None:
    with pytest.raises(ValueError, match="Unsupported log level"):
        configure_json_logger("test.invalid-level", "VERBOSE")
