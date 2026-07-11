import json
import logging
from uuid import UUID

import pytest
from test_api import jpeg_fixture, post_image

from app.logging_config import safe_log


@pytest.mark.parametrize(
    "field",
    ["filename", "image", "contour", "projected_width_mm", "recommended_size", "result_summary"],
)
def test_sensitive_log_fields_are_rejected(field: str) -> None:
    with pytest.raises(ValueError, match="Unsafe log fields"):
        safe_log(logging.getLogger("test"), logging.INFO, event="test", **{field: "secret"})


def test_measurement_logs_safe_stage_and_request_metrics(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="nailsize.inference"):
        response = post_image(jpeg_fixture(with_reference=True))

    records = [json.loads(record.message) for record in caplog.records]
    stages = {record.get("stage") for record in records if record["event"] == "stage_completed"}
    completed = next(record for record in records if record["event"] == "request_completed")

    assert stages == {"upload_decode", "capture_quality"}
    assert completed["status_code"] == 200
    assert completed["processing_ms"] >= 0
    assert response.headers["x-request-id"] == completed["request_id"]
    UUID(completed["request_id"])


def test_server_request_id_does_not_reflect_untrusted_header(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="nailsize.inference"):
        response = post_image(
            jpeg_fixture(), headers={"X-Request-ID": "private-customer-identifier"}
        )

    assert response.headers["x-request-id"] != "private-customer-identifier"
    assert "private-customer-identifier" not in caplog.text
