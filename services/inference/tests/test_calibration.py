import cv2
import numpy as np

from app.calibration import ISO_ID1_WIDTH_MM, detect_reference


def test_detects_synthetic_iso_reference() -> None:
    image = np.full((800, 1200, 3), 245, dtype=np.uint8)
    cv2.rectangle(image, (200, 220), (856, 634), (15, 15, 15), 8)
    calibration = detect_reference(image)
    assert calibration is not None
    assert calibration.pixels_per_mm == pytest.approx(656 / ISO_ID1_WIDTH_MM, rel=0.04)


import pytest  # noqa: E402


def test_rejects_scene_without_reference() -> None:
    image = np.full((600, 800, 3), 127, dtype=np.uint8)
    assert detect_reference(image) is None
