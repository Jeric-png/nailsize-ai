import hashlib
import json
from pathlib import Path

import cv2
import pytest

from app.quality import assess_capture, assess_nail_mask
from app.schemas import QualityIssueCode

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "golden_quality"
DETERMINISTIC_QUALITY_CODES = {
    QualityIssueCode.REFERENCE_MISSING,
    QualityIssueCode.REFERENCE_INVALID,
    QualityIssueCode.BLUR,
    QualityIssueCode.GLARE,
    QualityIssueCode.ANGLE_TOO_STEEP,
    QualityIssueCode.NAIL_CROPPED,
    QualityIssueCode.NAIL_OCCLUDED,
    QualityIssueCode.LOW_CONFIDENCE,
}


def cases() -> list[dict[str, str]]:
    return json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))


def test_manifest_covers_every_deterministic_quality_rejection() -> None:
    assert {QualityIssueCode(case["expected_code"]) for case in cases()} == (
        DETERMINISTIC_QUALITY_CODES
    )


@pytest.mark.parametrize("case", cases(), ids=lambda case: case["expected_code"])
def test_golden_quality_rejection(case: dict[str, str]) -> None:
    path = FIXTURE_DIR / case["file"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == case["sha256"]
    if case["evaluator"] == "capture":
        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        assert bgr is not None
        issues = assess_capture(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).issues
    else:
        mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        assert mask is not None
        issues = assess_nail_mask(mask)
    assert issues
    assert issues[0].code == QualityIssueCode(case["expected_code"])
