from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from .calibration import Calibration
from .hand_geometry import FingertipCrop


@dataclass(frozen=True)
class CalibratedNailMask:
    mask: NDArray[np.uint8]
    source_contour: tuple[tuple[float, float], ...]
    boundary_scale: float


def project_crop_mask(
    mask: NDArray[np.uint8],
    crop: FingertipCrop,
    image_shape: tuple[int, int],
    calibration: Calibration,
) -> CalibratedNailMask:
    """Map a crop-space mask back to the source image and calibrated card plane."""
    if mask.ndim != 2 or mask.shape != crop.rgb.shape[:2]:
        raise ValueError("Mask and fingertip crop dimensions must match")
    image_height, image_width = image_shape
    if image_height <= 0 or image_width <= 0:
        raise ValueError("Source image dimensions must be positive")
    contours, _ = cv2.findContours(
        (mask > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
    )
    if not contours:
        raise ValueError("Mask has no contour to project")
    contour = max(contours, key=cv2.contourArea).reshape(-1, 2).astype(np.float32)
    if len(contour) < 12:
        raise ValueError("Mask contour is too small to project")

    crop_height, crop_width = mask.shape
    destination = np.array(
        [
            [0, crop_height - 1],
            [crop_width - 1, crop_height - 1],
            [crop_width - 1, 0],
            [0, 0],
        ],
        dtype=np.float32,
    )
    source_quad = np.array(crop.source_quad, dtype=np.float32) * np.array(
        [image_width, image_height], dtype=np.float32
    )
    crop_to_source = cv2.getPerspectiveTransform(destination, source_quad)
    crop_to_calibrated = calibration.homography @ crop_to_source

    source_points = _transform(contour, crop_to_source)
    calibrated_points = _transform(contour, crop_to_calibrated)
    if (
        np.any(source_points[:, 0] < 0)
        or np.any(source_points[:, 0] > image_width - 1)
        or np.any(source_points[:, 1] < 0)
        or np.any(source_points[:, 1] > image_height - 1)
    ):
        raise ValueError("Projected nail contour leaves the source image")

    minimum = np.floor(calibrated_points.min(axis=0)) - 3
    maximum = np.ceil(calibrated_points.max(axis=0)) + 3
    output_width, output_height = (maximum - minimum + 1).astype(int)
    if output_width <= 0 or output_height <= 0 or output_width * output_height > 4_000_000:
        raise ValueError("Projected nail mask dimensions are unsafe")
    local_points = np.rint(calibrated_points - minimum).astype(np.int32)
    projected_mask = np.zeros((int(output_height), int(output_width)), dtype=np.uint8)
    cv2.fillPoly(projected_mask, [local_points], 1)

    x_offsets = _transform(contour + np.array([1.0, 0.0], dtype=np.float32), crop_to_calibrated)
    y_offsets = _transform(contour + np.array([0.0, 1.0], dtype=np.float32), crop_to_calibrated)
    boundary_scale = float(
        max(
            np.linalg.norm(x_offsets - calibrated_points, axis=1).max(),
            np.linalg.norm(y_offsets - calibrated_points, axis=1).max(),
        )
    )
    if not np.isfinite(boundary_scale) or not 0 < boundary_scale <= 100:
        raise ValueError("Crop-to-calibration boundary scale is unsafe")

    approximation = cv2.approxPolyDP(source_points.reshape(-1, 1, 2), 1.5, True).reshape(-1, 2)
    normalized = tuple(
        (float(point[0] / image_width), float(point[1] / image_height)) for point in approximation
    )
    return CalibratedNailMask(projected_mask, normalized, boundary_scale)


def _transform(points: NDArray[np.float32], homography: NDArray[np.float64]) -> NDArray[np.float32]:
    transformed = cv2.perspectiveTransform(points.reshape(1, -1, 2), homography)[0]
    if not np.isfinite(transformed).all():
        raise ValueError("Perspective projection produced non-finite coordinates")
    return transformed
