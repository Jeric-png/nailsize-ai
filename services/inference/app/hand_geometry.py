from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from .schemas import CaptureType

LANDMARK_COUNT = 21


@dataclass(frozen=True)
class NormalizedLandmark:
    x: float
    y: float
    z: float = 0.0


@dataclass(frozen=True)
class FingertipCrop:
    digit: str
    rgb: NDArray[np.uint8]
    source_quad: tuple[tuple[float, float], ...]
    clipped: bool


_DIGIT_LANDMARKS: Mapping[str, tuple[int, int, int, int]] = {
    "thumb": (1, 2, 3, 4),
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}

_CAPTURE_DIGITS: Mapping[CaptureType, tuple[str, ...]] = {
    CaptureType.LEFT_FINGERS: ("index", "middle", "ring", "pinky"),
    CaptureType.LEFT_THUMB: ("thumb",),
    CaptureType.RIGHT_FINGERS: ("index", "middle", "ring", "pinky"),
    CaptureType.RIGHT_THUMB: ("thumb",),
}


def expected_digits(capture_type: CaptureType) -> tuple[str, ...]:
    return _CAPTURE_DIGITS[capture_type]


def extract_fingertip_crops(
    rgb: NDArray[np.uint8],
    landmarks: Sequence[NormalizedLandmark],
    capture_type: CaptureType,
    *,
    output_size: tuple[int, int] = (160, 224),
) -> tuple[FingertipCrop, ...]:
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("A three-channel RGB image is required")
    if len(landmarks) != LANDMARK_COUNT:
        raise ValueError(f"Expected {LANDMARK_COUNT} hand landmarks")
    output_width, output_height = output_size
    if output_width <= 0 or output_height <= 0:
        raise ValueError("Crop dimensions must be positive")

    height, width = rgb.shape[:2]
    crops: list[FingertipCrop] = []
    for digit in expected_digits(capture_type):
        _, pip_index, dip_index, tip_index = _DIGIT_LANDMARKS[digit]
        pip = _pixel_point(landmarks[pip_index], width, height)
        dip = _pixel_point(landmarks[dip_index], width, height)
        tip = _pixel_point(landmarks[tip_index], width, height)
        axis = tip - pip
        axis_length = float(np.linalg.norm(axis))
        if axis_length < 2:
            raise ValueError(f"Degenerate landmarks for {digit}")
        axis /= axis_length
        perpendicular = np.array([-axis[1], axis[0]], dtype=np.float32)
        distal_length = max(float(np.linalg.norm(tip - dip)), axis_length * 0.45)
        half_width = max(8.0, distal_length * 0.85)
        half_length = max(12.0, distal_length * 1.35)
        center = tip - axis * distal_length * 0.35
        bottom = center - axis * half_length
        top = center + axis * half_length
        quad = np.array(
            [
                bottom - perpendicular * half_width,
                bottom + perpendicular * half_width,
                top + perpendicular * half_width,
                top - perpendicular * half_width,
            ],
            dtype=np.float32,
        )
        destination = np.array(
            [
                [0, output_height - 1],
                [output_width - 1, output_height - 1],
                [output_width - 1, 0],
                [0, 0],
            ],
            dtype=np.float32,
        )
        transform = cv2.getPerspectiveTransform(quad, destination)
        crop = cv2.warpPerspective(
            rgb,
            transform,
            (output_width, output_height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )
        clipped = bool(
            np.any(quad[:, 0] < 0)
            or np.any(quad[:, 0] > width - 1)
            or np.any(quad[:, 1] < 0)
            or np.any(quad[:, 1] > height - 1)
        )
        normalized_quad = tuple(
            (float(point[0] / width), float(point[1] / height)) for point in quad
        )
        crops.append(
            FingertipCrop(
                digit=digit,
                rgb=crop,
                source_quad=normalized_quad,
                clipped=clipped,
            )
        )
    return tuple(crops)


def _pixel_point(landmark: NormalizedLandmark, width: int, height: int) -> NDArray[np.float32]:
    if not np.isfinite((landmark.x, landmark.y, landmark.z)).all():
        raise ValueError("Landmarks must contain finite coordinates")
    return np.array([landmark.x * width, landmark.y * height], dtype=np.float32)
