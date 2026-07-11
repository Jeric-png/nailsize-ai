import cv2
import numpy as np
import pytest
from test_calibration import card_scene

from app.calibration import detect_reference
from app.measurement import (
    MeasurementConfidence,
    measure_maximum_transverse_chord,
    measure_projected_width,
    score_measurement_confidence,
)


@pytest.mark.parametrize("angle", [0, 23, 67, 90, 135])
def test_measures_rotated_nail_mask_transverse_width(angle: float) -> None:
    mask = np.zeros((320, 320), dtype=np.uint8)
    cv2.ellipse(mask, (160, 160), (30, 85), angle, 0, 360, 255, -1)
    measurement = measure_maximum_transverse_chord(mask)
    assert measurement.width_px == pytest.approx(60, abs=2.5)
    axis_length = np.hypot(*measurement.longitudinal_axis)
    assert axis_length == pytest.approx(1.0, abs=1e-6)


def test_ignores_extreme_tip_and_base_when_selecting_chord() -> None:
    mask = np.zeros((240, 160), dtype=np.uint8)
    points = np.array([[80, 20], [115, 70], [105, 200], [55, 200], [45, 70]])
    cv2.fillConvexPoly(mask, points, 255)
    measurement = measure_maximum_transverse_chord(mask)
    assert 58 <= measurement.width_px <= 72


def test_rejects_empty_or_tiny_mask() -> None:
    with pytest.raises(ValueError, match="no measurable contour"):
        measure_maximum_transverse_chord(np.zeros((20, 20), dtype=np.uint8))
    tiny = np.zeros((20, 20), dtype=np.uint8)
    tiny[10:12, 10:12] = 255
    with pytest.raises(ValueError, match="too small"):
        measure_maximum_transverse_chord(tiny)


def test_converts_rectified_chord_to_projected_millimetres() -> None:
    calibration = detect_reference(card_scene())
    assert calibration is not None
    mask = np.zeros((320, 320), dtype=np.uint8)
    cv2.ellipse(mask, (160, 160), (71, 110), 0, 0, 360, 255, -1)
    projected = measure_projected_width(
        mask,
        calibration,
        segmentation_boundary_error_px=3.0,
        segmentation_confidence=0.96,
    )
    assert projected.width_mm == pytest.approx(14.2, abs=0.3)
    assert 0.3 <= projected.uncertainty_mm <= 0.5
    assert projected.confidence == MeasurementConfidence.HIGH


@pytest.mark.parametrize(
    ("uncertainty", "score", "expected"),
    [
        (0.4, 0.90, MeasurementConfidence.HIGH),
        (0.6, 0.80, MeasurementConfidence.MEDIUM),
        (0.8, 0.99, MeasurementConfidence.LOW),
        (0.2, 0.70, MeasurementConfidence.LOW),
    ],
)
def test_scores_measurement_confidence(
    uncertainty: float,
    score: float,
    expected: MeasurementConfidence,
) -> None:
    assert score_measurement_confidence(uncertainty, score) == expected


@pytest.mark.parametrize(("uncertainty", "score"), [(-0.1, 0.9), (0.1, -0.1), (0.1, 1.1)])
def test_rejects_invalid_confidence_inputs(uncertainty: float, score: float) -> None:
    with pytest.raises(ValueError):
        score_measurement_confidence(uncertainty, score)
