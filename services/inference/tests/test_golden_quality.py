import hashlib
import json
from pathlib import Path

import cv2
import pytest
from test_hand_geometry import hand_landmarks

from app.hand_landmarks import HandDetection, MediaPipeHandDetector
from app.pipeline import run_measurement_pipeline
from app.quality import assess_capture, assess_nail_mask
from app.schemas import CaptureType, QualityIssue, QualityIssueCode
from app.segmentation import SegmentationResult

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "golden_quality"
HAND_MODEL = Path(__file__).parents[1] / "models" / "hand_landmarker.task"
UNIMPLEMENTED_QUALITY_CODES = {QualityIssueCode.UNSUPPORTED_NAIL_CONDITION}
CURRENTLY_EMITTED_QUALITY_CODES = set(QualityIssueCode) - UNIMPLEMENTED_QUALITY_CODES


class StaticHandDetector:
    def __init__(self, detection: HandDetection) -> None:
        self.detection = detection

    def detect(self, _rgb):
        return self.detection


class StaticSegmenter:
    def __init__(self, mask) -> None:
        self.mask = mask

    def segment(self, _rgb):
        return SegmentationResult(self.mask, 0.98)


class UnusedSegmenter:
    def segment(self, _rgb):
        raise AssertionError("Segmentation must not run without a detected hand")


def cases() -> list[dict[str, str]]:
    return json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))


def test_manifest_covers_every_currently_emitted_quality_rejection() -> None:
    assert {QualityIssueCode(case["expected_code"]) for case in cases()} == (
        CURRENTLY_EMITTED_QUALITY_CODES
    )
    assert {case["file"] for case in cases()} == {path.name for path in FIXTURE_DIR.glob("*.png")}


@pytest.mark.parametrize("case", cases(), ids=lambda case: case["expected_code"])
def test_golden_quality_rejection(case: dict[str, str]) -> None:
    path = FIXTURE_DIR / case["file"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == case["sha256"]
    if case["evaluator"] == "capture":
        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        assert bgr is not None
        issues = assess_capture(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).issues
    elif case["evaluator"] == "mask":
        mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        assert mask is not None
        issues = assess_nail_mask(mask)
    elif case["evaluator"] == "pipeline_no_hand":
        issues = pipeline_no_hand_issues(path)
    elif case["evaluator"] == "pipeline_outside_chart":
        issues = pipeline_outside_chart_issues(path)
    else:
        raise AssertionError(f"Unknown golden evaluator: {case['evaluator']}")
    assert issues
    assert issues[0].code == QualityIssueCode(case["expected_code"])


def pipeline_no_hand_issues(path: Path) -> tuple[QualityIssue, ...]:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    assert bgr is not None
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    capture = assess_capture(rgb)
    assert capture.calibration is not None
    checksum = hashlib.sha256(HAND_MODEL.read_bytes()).hexdigest()
    with MediaPipeHandDetector(HAND_MODEL, sha256=checksum) as detector:
        result = run_measurement_pipeline(
            rgb,
            CaptureType.LEFT_THUMB,
            capture.calibration,
            detector,
            UnusedSegmenter(),
            segmentation_boundary_error_px=0.5,
        )
    assert result.issue is not None
    return (result.issue,)


def pipeline_outside_chart_issues(path: Path) -> tuple[QualityIssue, ...]:
    mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    capture_bgr = cv2.imread(str(FIXTURE_DIR / "wrong-nail-count.png"), cv2.IMREAD_COLOR)
    assert mask is not None and capture_bgr is not None
    rgb = cv2.cvtColor(capture_bgr, cv2.COLOR_BGR2RGB)
    capture = assess_capture(rgb)
    assert capture.calibration is not None
    detection = HandDetection(tuple(hand_landmarks(tip_y=0.28)), "Left", 0.99)
    result = run_measurement_pipeline(
        rgb,
        CaptureType.LEFT_THUMB,
        capture.calibration,
        StaticHandDetector(detection),
        StaticSegmenter(mask),
        segmentation_boundary_error_px=0.5,
    )
    assert result.issue is not None
    return (result.issue,)
