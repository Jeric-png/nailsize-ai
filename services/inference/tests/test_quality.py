import cv2
import numpy as np
import pytest
from test_calibration import card_scene

from app.quality import (
    assess_capture,
    assess_nail_mask,
    glare_fraction,
    nail_mask_occlusion_fraction,
)
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


def test_rejects_clipped_fingertip_crop_even_when_mask_does_not_touch_border() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    cv2.ellipse(mask, (50, 50), (18, 32), 0, 0, 360, 255, -1)
    issues = assess_nail_mask(mask, crop_clipped=True)
    assert issues[0].code == QualityIssueCode.NAIL_CROPPED


def test_rejects_nail_mask_with_boundary_occlusion() -> None:
    mask = np.zeros((120, 120), dtype=np.uint8)
    cv2.ellipse(mask, (60, 60), (30, 45), 0, 0, 360, 255, -1)
    cv2.rectangle(mask, (55, 15), (85, 75), 0, -1)
    assert nail_mask_occlusion_fraction(mask) > 0.12
    issues = assess_nail_mask(mask)
    assert issues[0].code == QualityIssueCode.NAIL_OCCLUDED


def test_rejects_nail_mask_with_surface_occlusion() -> None:
    mask = np.zeros((120, 120), dtype=np.uint8)
    cv2.ellipse(mask, (60, 60), (30, 45), 0, 0, 360, 255, -1)
    cv2.circle(mask, (60, 60), 15, 0, -1)
    assert nail_mask_occlusion_fraction(mask) > 0.12
    issues = assess_nail_mask(mask)
    assert issues[0].code == QualityIssueCode.NAIL_OCCLUDED


def test_accepts_sufficient_uncropped_mask() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    cv2.ellipse(mask, (50, 50), (18, 32), 0, 0, 360, 255, -1)
    assert nail_mask_occlusion_fraction(mask) < 0.02
    assert assess_nail_mask(mask) == ()


@pytest.mark.parametrize(
    ("mask", "kwargs"),
    [
        (np.zeros((0, 0), dtype=np.uint8), {}),
        (np.zeros((10, 10, 1), dtype=np.uint8), {}),
        (np.zeros((10, 10), dtype=np.uint8), {"minimum_pixels": 0}),
        (np.zeros((10, 10), dtype=np.uint8), {"maximum_occlusion_fraction": 1.0}),
    ],
)
def test_rejects_invalid_nail_quality_inputs(mask: np.ndarray, kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        assess_nail_mask(mask, **kwargs)
