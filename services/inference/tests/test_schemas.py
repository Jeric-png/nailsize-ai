import pytest
from pydantic import ValidationError

from app.schemas import MeasureResponse


def response_payload(**overrides):
    payload = {
        "status": "retake",
        "request_id": "request-1",
        "capture_type": "left_thumb",
        "measurements": [],
        "quality_issues": [
            {
                "code": "LOW_CONFIDENCE",
                "message": "Not safe to measure.",
                "correction": "Retake the photo.",
            }
        ],
        "model_version": "candidate",
        "processing_ms": 10,
    }
    payload.update(overrides)
    return payload


def thumb_measurement():
    return {
        "digit": "thumb",
        "projected_width_mm": 14.2,
        "uncertainty_mm": 0.3,
        "recommended_size": "4",
        "alternate_size": None,
        "confidence": "high",
        "contour": [(0.1, 0.2), (0.2, 0.2), (0.2, 0.4)],
    }


def test_retake_cannot_contain_measurements_or_omit_issue() -> None:
    with pytest.raises(ValidationError, match="Retake responses"):
        MeasureResponse.model_validate(response_payload(measurements=[thumb_measurement()]))
    with pytest.raises(ValidationError, match="Retake responses"):
        MeasureResponse.model_validate(response_payload(quality_issues=[]))


def test_success_requires_exact_semantic_measurement_set_and_no_issues() -> None:
    valid = MeasureResponse.model_validate(
        response_payload(status="ok", measurements=[thumb_measurement()], quality_issues=[])
    )
    assert valid.status == "ok"

    with pytest.raises(ValidationError, match="every expected measurement"):
        MeasureResponse.model_validate(
            response_payload(status="ok", measurements=[], quality_issues=[])
        )
    with pytest.raises(ValidationError, match="every expected measurement"):
        MeasureResponse.model_validate(
            response_payload(status="ok", measurements=[thumb_measurement()])
        )
