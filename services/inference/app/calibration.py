from dataclasses import dataclass
from enum import StrEnum

import cv2
import numpy as np
from numpy.typing import NDArray

ISO_ID1_WIDTH_MM = 85.60
ISO_ID1_HEIGHT_MM = 53.98
ISO_ID1_ASPECT = ISO_ID1_WIDTH_MM / ISO_ID1_HEIGHT_MM
RECTIFIED_PIXELS_PER_MM = 10.0
RECTIFIED_WIDTH = round(ISO_ID1_WIDTH_MM * RECTIFIED_PIXELS_PER_MM)
RECTIFIED_HEIGHT = round(ISO_ID1_HEIGHT_MM * RECTIFIED_PIXELS_PER_MM)


class ReferenceFailure(StrEnum):
    MISSING = "missing"
    INVALID = "invalid"
    CROPPED = "cropped"
    ANGLE_TOO_STEEP = "angle_too_steep"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class Calibration:
    corners: NDArray[np.float32]
    homography: NDArray[np.float64]
    pixels_per_mm: float
    corner_error_px: float
    relative_scale_uncertainty: float
    perspective_ratio: float


@dataclass(frozen=True)
class ReferenceAnalysis:
    calibration: Calibration | None
    failure: ReferenceFailure | None


@dataclass(frozen=True)
class RectifiedPlane:
    rgb: NDArray[np.uint8]
    homography: NDArray[np.float64]
    pixels_per_mm: float


@dataclass(frozen=True)
class _Candidate:
    contour: NDArray[np.int32]
    corners: NDArray[np.float32]
    area: float
    aspect_error: float
    opposite_error: float
    perspective_ratio: float


def _order_corners(points: NDArray[np.float32]) -> NDArray[np.float32]:
    ordered = np.zeros((4, 2), dtype=np.float32)
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).reshape(-1)
    ordered[0] = points[np.argmin(sums)]
    ordered[2] = points[np.argmax(sums)]
    ordered[1] = points[np.argmin(differences)]
    ordered[3] = points[np.argmax(differences)]
    horizontal = (
        np.linalg.norm(ordered[1] - ordered[0]) + np.linalg.norm(ordered[2] - ordered[3])
    ) / 2
    vertical = (
        np.linalg.norm(ordered[3] - ordered[0]) + np.linalg.norm(ordered[2] - ordered[1])
    ) / 2
    if horizontal < vertical:
        ordered = np.roll(ordered, -1, axis=0)
    return ordered


def _edge_lengths(corners: NDArray[np.float32]) -> tuple[float, float, float, float]:
    top = float(np.linalg.norm(corners[1] - corners[0]))
    right = float(np.linalg.norm(corners[2] - corners[1]))
    bottom = float(np.linalg.norm(corners[2] - corners[3]))
    left = float(np.linalg.norm(corners[3] - corners[0]))
    return top, right, bottom, left


def _point_to_segment_distance(
    points: NDArray[np.float32], start: NDArray[np.float32], end: NDArray[np.float32]
) -> NDArray[np.float32]:
    segment = end - start
    denominator = float(np.dot(segment, segment))
    if denominator == 0:
        return np.linalg.norm(points - start, axis=1)
    projection = np.clip(((points - start) @ segment) / denominator, 0.0, 1.0)
    closest = start + projection[:, None] * segment
    return np.linalg.norm(points - closest, axis=1)


def _corner_fit_error(contour: NDArray[np.int32], corners: NDArray[np.float32]) -> float:
    points = contour.reshape(-1, 2).astype(np.float32)
    distances = np.stack(
        [
            _point_to_segment_distance(points, corners[index], corners[(index + 1) % 4])
            for index in range(4)
        ]
    )
    minimum = distances.min(axis=0)
    return float(np.sqrt(np.mean(np.square(minimum))))


def _find_candidates(rgb: NDArray[np.uint8]) -> list[_Candidate]:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 140)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = rgb.shape[0] * rgb.shape[1]
    candidates: list[_Candidate] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if not 0.03 * image_area <= area <= 0.75 * image_area:
            continue
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue
        corners = _order_corners(polygon.reshape(4, 2).astype(np.float32))
        top, right, bottom, left = _edge_lengths(corners)
        mean_width = (top + bottom) / 2
        mean_height = (left + right) / 2
        if mean_height <= 0 or min(top, right, bottom, left) <= 8:
            continue
        aspect = mean_width / mean_height
        aspect_error = abs(aspect - ISO_ID1_ASPECT) / ISO_ID1_ASPECT
        opposite_error = max(
            abs(top - bottom) / max(mean_width, 1),
            abs(left - right) / max(mean_height, 1),
        )
        perspective_ratio = min(top, bottom) / max(top, bottom)
        perspective_ratio = min(
            perspective_ratio,
            min(left, right) / max(left, right),
        )
        candidates.append(
            _Candidate(
                contour=contour,
                corners=corners,
                area=area,
                aspect_error=aspect_error,
                opposite_error=opposite_error,
                perspective_ratio=perspective_ratio,
            )
        )
    return candidates


def analyze_reference(rgb: NDArray[np.uint8]) -> ReferenceAnalysis:
    candidates = _find_candidates(rgb)
    if not candidates:
        return ReferenceAnalysis(None, ReferenceFailure.MISSING)

    plausible = [candidate for candidate in candidates if candidate.aspect_error <= 0.20]
    if not plausible:
        return ReferenceAnalysis(None, ReferenceFailure.INVALID)
    candidate = max(plausible, key=lambda item: item.area)

    height, width = rgb.shape[:2]
    margin = max(3.0, min(width, height) * 0.0125)
    x_coordinates = candidate.corners[:, 0]
    y_coordinates = candidate.corners[:, 1]
    if (
        x_coordinates.min() <= margin
        or y_coordinates.min() <= margin
        or x_coordinates.max() >= width - 1 - margin
        or y_coordinates.max() >= height - 1 - margin
    ):
        return ReferenceAnalysis(None, ReferenceFailure.CROPPED)
    if candidate.perspective_ratio < 0.55 or candidate.opposite_error > 0.45:
        return ReferenceAnalysis(None, ReferenceFailure.ANGLE_TOO_STEEP)
    if candidate.aspect_error > 0.10:
        return ReferenceAnalysis(None, ReferenceFailure.INVALID)

    destination = np.array(
        [
            [0.0, 0.0],
            [RECTIFIED_WIDTH - 1.0, 0.0],
            [RECTIFIED_WIDTH - 1.0, RECTIFIED_HEIGHT - 1.0],
            [0.0, RECTIFIED_HEIGHT - 1.0],
        ],
        dtype=np.float32,
    )
    homography = cv2.getPerspectiveTransform(candidate.corners, destination)
    if not np.isfinite(homography).all() or np.linalg.cond(homography) > 1e8:
        return ReferenceAnalysis(None, ReferenceFailure.UNCERTAIN)

    corner_error = _corner_fit_error(candidate.contour, candidate.corners)
    top, _, bottom, _ = _edge_lengths(candidate.corners)
    mean_width = (top + bottom) / 2
    relative_uncertainty = max(0.002, corner_error / max(mean_width, 1))
    if relative_uncertainty > 0.035:
        return ReferenceAnalysis(None, ReferenceFailure.UNCERTAIN)

    pixels_per_mm = (
        (RECTIFIED_WIDTH - 1) / ISO_ID1_WIDTH_MM + (RECTIFIED_HEIGHT - 1) / ISO_ID1_HEIGHT_MM
    ) / 2
    calibration = Calibration(
        corners=candidate.corners,
        homography=homography,
        pixels_per_mm=pixels_per_mm,
        corner_error_px=corner_error,
        relative_scale_uncertainty=relative_uncertainty,
        perspective_ratio=candidate.perspective_ratio,
    )
    return ReferenceAnalysis(calibration, None)


def detect_reference(rgb: NDArray[np.uint8]) -> Calibration | None:
    return analyze_reference(rgb).calibration


def rectify_plane(rgb: NDArray[np.uint8], calibration: Calibration) -> RectifiedPlane:
    """Rectify the full card/hand plane without clipping content outside the card."""
    height, width = rgb.shape[:2]
    image_corners = np.array(
        [[[0.0, 0.0], [width - 1.0, 0.0], [width - 1.0, height - 1.0], [0.0, height - 1.0]]],
        dtype=np.float32,
    )
    transformed = cv2.perspectiveTransform(image_corners, calibration.homography)[0]
    minimum = np.floor(transformed.min(axis=0))
    maximum = np.ceil(transformed.max(axis=0))
    output_width, output_height = (maximum - minimum + 1).astype(int)
    if output_width <= 0 or output_height <= 0 or output_width * output_height > 40_000_000:
        raise ValueError("Rectified plane dimensions are unsafe")
    translation = np.array(
        [[1.0, 0.0, -minimum[0]], [0.0, 1.0, -minimum[1]], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    full_homography = translation @ calibration.homography
    rectified = cv2.warpPerspective(
        rgb,
        full_homography,
        (int(output_width), int(output_height)),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )
    return RectifiedPlane(rectified, full_homography, calibration.pixels_per_mm)


def propagate_width_uncertainty(
    width_px: float,
    calibration: Calibration,
    segmentation_boundary_error_px: float,
) -> float:
    if width_px <= 0 or segmentation_boundary_error_px < 0:
        raise ValueError("Width must be positive and boundary error non-negative")
    width_mm = width_px / calibration.pixels_per_mm
    boundary_mm = segmentation_boundary_error_px / calibration.pixels_per_mm
    scale_mm = width_mm * calibration.relative_scale_uncertainty
    return float(np.hypot(boundary_mm, scale_mm))


def blur_score(rgb: NDArray[np.uint8]) -> float:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())
