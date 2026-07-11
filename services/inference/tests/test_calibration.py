import cv2
import numpy as np
import pytest

from app.calibration import (
    ISO_ID1_HEIGHT_MM,
    ISO_ID1_WIDTH_MM,
    RECTIFIED_HEIGHT,
    RECTIFIED_WIDTH,
    ReferenceFailure,
    analyze_reference,
    detect_reference,
    propagate_width_uncertainty,
    rectify_plane,
)


def card_scene(
    corners: np.ndarray | None = None,
    *,
    size: tuple[int, int] = (900, 1200),
) -> np.ndarray:
    height, width = size
    image = np.full((height, width, 3), 210, dtype=np.uint8)
    for x in range(0, width, 24):
        cv2.line(image, (x, 0), (x, height - 1), (190, 190, 190), 1)
    for y in range(0, height, 24):
        cv2.line(image, (0, y), (width - 1, y), (190, 190, 190), 1)
    if corners is None:
        corners = np.array([[200, 220], [856, 220], [856, 634], [200, 634]])
    cv2.fillConvexPoly(image, corners.astype(np.int32), (238, 238, 238))
    cv2.polylines(image, [corners.astype(np.int32)], True, (15, 15, 15), 8)
    return image


def test_detects_synthetic_iso_reference() -> None:
    calibration = detect_reference(card_scene())
    assert calibration is not None
    assert calibration.pixels_per_mm == pytest.approx(10.0, rel=0.01)
    assert calibration.corner_error_px < 2.0
    assert calibration.relative_scale_uncertainty >= 0.002


def test_homography_maps_card_to_known_physical_rectangle() -> None:
    calibration = detect_reference(card_scene())
    assert calibration is not None
    transformed = cv2.perspectiveTransform(
        calibration.corners.reshape(1, 4, 2), calibration.homography
    )[0]
    expected = np.array(
        [
            [0, 0],
            [RECTIFIED_WIDTH - 1, 0],
            [RECTIFIED_WIDTH - 1, RECTIFIED_HEIGHT - 1],
            [0, RECTIFIED_HEIGHT - 1],
        ],
        dtype=np.float32,
    )
    assert transformed == pytest.approx(expected, abs=0.05)
    assert (RECTIFIED_WIDTH - 1) / calibration.pixels_per_mm == pytest.approx(
        ISO_ID1_WIDTH_MM, abs=0.1
    )
    assert (RECTIFIED_HEIGHT - 1) / calibration.pixels_per_mm == pytest.approx(
        ISO_ID1_HEIGHT_MM, abs=0.1
    )


def test_rectifies_perspective_scene_without_clipping_full_plane() -> None:
    corners = np.array([[260, 180], [920, 250], [850, 680], [190, 610]])
    image = card_scene(corners)
    calibration = detect_reference(image)
    assert calibration is not None
    rectified = rectify_plane(image, calibration)
    assert rectified.rgb.shape[0] >= RECTIFIED_HEIGHT
    assert rectified.rgb.shape[1] >= RECTIFIED_WIDTH
    transformed = cv2.perspectiveTransform(
        calibration.corners.reshape(1, 4, 2), rectified.homography
    )[0]
    widths = [
        np.linalg.norm(transformed[1] - transformed[0]),
        np.linalg.norm(transformed[2] - transformed[3]),
    ]
    assert np.mean(widths) / rectified.pixels_per_mm == pytest.approx(ISO_ID1_WIDTH_MM, abs=0.15)


def test_detects_reference_after_lossy_jpeg_compression() -> None:
    image = card_scene(np.array([[260, 180], [920, 250], [850, 680], [190, 610]]))
    encoded, payload = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 28])
    assert encoded
    decoded = cv2.imdecode(payload, cv2.IMREAD_COLOR)
    calibration = detect_reference(decoded)
    assert calibration is not None
    assert calibration.pixels_per_mm == pytest.approx(10.0, rel=0.01)


def test_rejects_cropped_reference() -> None:
    image = card_scene(np.array([[0, 220], [656, 220], [656, 634], [0, 634]]))
    analysis = analyze_reference(image)
    assert analysis.calibration is None
    assert analysis.failure == ReferenceFailure.CROPPED


def test_rejects_steep_perspective() -> None:
    corners = np.array([[180, 220], [830, 220], [660, 520], [350, 520]])
    analysis = analyze_reference(card_scene(corners))
    assert analysis.calibration is None
    assert analysis.failure == ReferenceFailure.ANGLE_TOO_STEEP


def test_rejects_wrong_aspect_rectangle() -> None:
    corners = np.array([[250, 180], [750, 180], [750, 680], [250, 680]])
    analysis = analyze_reference(card_scene(corners))
    assert analysis.calibration is None
    assert analysis.failure == ReferenceFailure.INVALID


def test_rejects_scene_without_reference() -> None:
    image = np.full((600, 800, 3), 127, dtype=np.uint8)
    cv2.circle(image, (400, 300), 130, (20, 20, 20), 6)
    analysis = analyze_reference(image)
    assert analysis.calibration is None
    assert analysis.failure == ReferenceFailure.MISSING


def test_propagates_boundary_and_calibration_uncertainty() -> None:
    calibration = detect_reference(card_scene())
    assert calibration is not None
    uncertainty = propagate_width_uncertainty(
        width_px=142.0,
        calibration=calibration,
        segmentation_boundary_error_px=3.0,
    )
    assert uncertainty >= 3.0 / calibration.pixels_per_mm
    assert uncertainty < 0.5


@pytest.mark.parametrize(("width", "boundary"), [(0, 1), (20, -1)])
def test_rejects_invalid_uncertainty_inputs(width: float, boundary: float) -> None:
    calibration = detect_reference(card_scene())
    assert calibration is not None
    with pytest.raises(ValueError):
        propagate_width_uncertainty(width, calibration, boundary)
