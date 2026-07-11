import numpy as np
import pytest

from app.hand_geometry import NormalizedLandmark, expected_digits, extract_fingertip_crops
from app.schemas import CaptureType


def hand_landmarks(*, tip_y: float = 0.24) -> list[NormalizedLandmark]:
    points = [NormalizedLandmark(0.5, 0.9) for _ in range(21)]
    digit_x = {"thumb": 0.18, "index": 0.34, "middle": 0.47, "ring": 0.60, "pinky": 0.73}
    indices = {
        "thumb": (1, 2, 3, 4),
        "index": (5, 6, 7, 8),
        "middle": (9, 10, 11, 12),
        "ring": (13, 14, 15, 16),
        "pinky": (17, 18, 19, 20),
    }
    for digit, landmark_indices in indices.items():
        x = digit_x[digit]
        for index, y in zip(landmark_indices, (0.65, 0.50, 0.36, tip_y), strict=True):
            points[index] = NormalizedLandmark(x, y)
    return points


@pytest.mark.parametrize(
    "capture_type",
    [CaptureType.LEFT_FINGERS, CaptureType.RIGHT_FINGERS],
)
def test_four_finger_crops_have_semantic_order_and_fixed_shape(capture_type: CaptureType) -> None:
    image = np.full((800, 1000, 3), 127, dtype=np.uint8)
    crops = extract_fingertip_crops(image, hand_landmarks(), capture_type)
    assert tuple(crop.digit for crop in crops) == ("index", "middle", "ring", "pinky")
    assert all(crop.rgb.shape == (224, 160, 3) for crop in crops)
    assert all(not crop.clipped for crop in crops)


@pytest.mark.parametrize("capture_type", [CaptureType.LEFT_THUMB, CaptureType.RIGHT_THUMB])
def test_thumb_capture_only_returns_thumb(capture_type: CaptureType) -> None:
    image = np.full((800, 1000, 3), 127, dtype=np.uint8)
    crops = extract_fingertip_crops(image, hand_landmarks(), capture_type)
    assert tuple(crop.digit for crop in crops) == ("thumb",)


def test_capture_type_not_handedness_controls_identity() -> None:
    assert expected_digits(CaptureType.LEFT_FINGERS) == expected_digits(CaptureType.RIGHT_FINGERS)
    assert expected_digits(CaptureType.LEFT_THUMB) == ("thumb",)


def test_marks_crop_when_fingertip_reaches_image_boundary() -> None:
    image = np.full((800, 1000, 3), 127, dtype=np.uint8)
    crops = extract_fingertip_crops(
        image,
        hand_landmarks(tip_y=0.01),
        CaptureType.LEFT_FINGERS,
    )
    assert all(crop.clipped for crop in crops)


def test_rejects_incomplete_or_degenerate_landmarks() -> None:
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="Expected 21"):
        extract_fingertip_crops(image, hand_landmarks()[:-1], CaptureType.LEFT_THUMB)
    collapsed = [NormalizedLandmark(0.5, 0.5) for _ in range(21)]
    with pytest.raises(ValueError, match="Degenerate"):
        extract_fingertip_crops(image, collapsed, CaptureType.LEFT_THUMB)
