import cv2
import numpy as np
import pytest

from app.calibration import Calibration
from app.hand_geometry import FingertipCrop
from app.measurement import measure_maximum_transverse_chord
from app.projection import project_crop_mask


def identity_calibration() -> Calibration:
    return Calibration(
        corners=np.zeros((4, 2), dtype=np.float32),
        homography=np.eye(3),
        pixels_per_mm=10.0,
        corner_error_px=0.0,
        relative_scale_uncertainty=0.002,
        perspective_ratio=1.0,
    )


def test_projects_crop_mask_to_source_and_calibrated_plane() -> None:
    rgb = np.zeros((224, 160, 3), dtype=np.uint8)
    mask = np.zeros((224, 160), dtype=np.uint8)
    cv2.ellipse(mask, (80, 112), (20, 60), 0, 0, 360, 1, -1)
    crop = FingertipCrop(
        digit="index",
        rgb=rgb,
        source_quad=((0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)),
        clipped=False,
    )

    projected = project_crop_mask(mask, crop, (448, 320), identity_calibration())
    chord = measure_maximum_transverse_chord(projected.mask)

    assert chord.width_px == pytest.approx(80, abs=4)
    assert projected.boundary_scale == pytest.approx(2.0, rel=0.02)
    assert len(projected.source_contour) >= 8
    assert all(0 <= coordinate <= 1 for point in projected.source_contour for coordinate in point)


def test_projection_rejects_mismatched_or_empty_masks() -> None:
    crop = FingertipCrop(
        digit="thumb",
        rgb=np.zeros((224, 160, 3), dtype=np.uint8),
        source_quad=((0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)),
        clipped=False,
    )
    with pytest.raises(ValueError, match="dimensions"):
        project_crop_mask(
            np.zeros((10, 10), dtype=np.uint8), crop, (448, 320), identity_calibration()
        )
    with pytest.raises(ValueError, match="no contour"):
        project_crop_mask(
            np.zeros((224, 160), dtype=np.uint8), crop, (448, 320), identity_calibration()
        )
