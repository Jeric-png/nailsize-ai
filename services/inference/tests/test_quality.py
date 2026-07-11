import cv2
import numpy as np
from test_calibration import card_scene

from app.quality import assess_capture, assess_nail_mask, glare_fraction
from app.schemas import QualityIssueCode


def test_rejects_blur_before_calibration() -> None:
    blurred = cv2.GaussianBlur(card_scene(), (91, 91), 25)
    result = assess_capture(blurred)
    assert result.calibration is None
    assert result.issues[0].code == QualityIssueCode.BLUR


def test_rejects_localized_glare_but_not_uniform_backdrop() -> None:
    image = card_scene()
    cv2.circle(image, (1050, 110), 80, (255, 255, 255), -1)
    assert glare_fraction(image) > 0.015
    result = assess_capture(image)
    assert result.calibration is None
    assert result.issues[0].code == QualityIssueCode.GLARE


def test_accepts_capture_quality_when_reference_is_valid() -> None:
    result = assess_capture(card_scene())
    assert result.calibration is not None
    assert result.issues == ()


def test_maps_steep_reference_to_specific_issue() -> None:
    corners = np.array([[180, 220], [830, 220], [660, 520], [350, 520]])
    result = assess_capture(card_scene(corners))
    assert result.issues[0].code == QualityIssueCode.ANGLE_TOO_STEEP


def test_rejects_small_nail_mask() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    cv2.circle(mask, (50, 50), 5, 255, -1)
    issues = assess_nail_mask(mask)
    assert issues[0].code == QualityIssueCode.LOW_CONFIDENCE


def test_rejects_cropped_nail_mask() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    cv2.rectangle(mask, (0, 20), (40, 80), 255, -1)
    issues = assess_nail_mask(mask)
    assert issues[0].code == QualityIssueCode.NAIL_CROPPED


def test_accepts_sufficient_uncropped_mask() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    cv2.ellipse(mask, (50, 50), (18, 32), 0, 0, 360, 255, -1)
    assert assess_nail_mask(mask) == ()
