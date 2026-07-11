import cv2
import numpy as np
from test_calibration import card_scene
from test_hand_geometry import hand_landmarks

from app.calibration import detect_reference
from app.hand_landmarks import HandDetection
from app.pipeline import run_measurement_pipeline
from app.schemas import CaptureType, QualityIssueCode
from app.segmentation import SegmentationResult


class FakeHandDetector:
    def __init__(self, detection: HandDetection | None) -> None:
        self.detection = detection

    def detect(self, _rgb):
        return self.detection


class FakeSegmenter:
    def __init__(self, *, confidence: float = 0.98, width: int = 45) -> None:
        self.confidence = confidence
        self.width = width

    def segment(self, _rgb):
        mask = np.zeros((224, 160), dtype=np.uint8)
        cv2.ellipse(mask, (80, 112), (self.width, 62), 0, 0, 360, 1, -1)
        return SegmentationResult(mask, self.confidence)


def valid_detection() -> HandDetection:
    return HandDetection(tuple(hand_landmarks(tip_y=0.28)), "Left", 0.99)


def test_pipeline_returns_calibrated_measurements_in_semantic_order() -> None:
    image = card_scene()
    calibration = detect_reference(image)
    assert calibration is not None

    result = run_measurement_pipeline(
        image,
        CaptureType.LEFT_FINGERS,
        calibration,
        FakeHandDetector(valid_detection()),
        FakeSegmenter(),
        segmentation_boundary_error_px=0.5,
    )

    assert result.issue is None
    assert tuple(item.digit for item in result.measurements) == ("index", "middle", "ring", "pinky")
    assert all(9 <= item.projected_width_mm <= 18 for item in result.measurements)
    assert all(item.confidence in {"high", "medium"} for item in result.measurements)
    assert all(item.contour for item in result.measurements)
    assert set(result.stage_timings_ms) == {
        "hand_landmarks",
        "crop_extraction",
        "segmentation",
        "calibrated_measurement",
    }


def test_pipeline_rejects_missing_hand_and_low_segmentation_confidence() -> None:
    image = card_scene()
    calibration = detect_reference(image)
    assert calibration is not None

    missing = run_measurement_pipeline(
        image,
        CaptureType.LEFT_THUMB,
        calibration,
        FakeHandDetector(None),
        FakeSegmenter(),
        segmentation_boundary_error_px=0.5,
    )
    assert missing.issue is not None
    assert missing.issue.code == QualityIssueCode.WRONG_NAIL_COUNT
    assert not missing.measurements

    uncertain = run_measurement_pipeline(
        image,
        CaptureType.LEFT_THUMB,
        calibration,
        FakeHandDetector(valid_detection()),
        FakeSegmenter(confidence=0.70),
        segmentation_boundary_error_px=0.5,
    )
    assert uncertain.issue is not None
    assert uncertain.issue.code == QualityIssueCode.LOW_CONFIDENCE
    assert not uncertain.measurements


def test_pipeline_rejects_unvalidated_boundary_error() -> None:
    image = card_scene()
    calibration = detect_reference(image)
    assert calibration is not None

    for boundary_error in (0.0, float("nan")):
        try:
            run_measurement_pipeline(
                image,
                CaptureType.LEFT_THUMB,
                calibration,
                FakeHandDetector(valid_detection()),
                FakeSegmenter(),
                segmentation_boundary_error_px=boundary_error,
            )
        except ValueError as error:
            assert "validated positive" in str(error)
        else:
            raise AssertionError("Unvalidated boundary error must fail closed")
