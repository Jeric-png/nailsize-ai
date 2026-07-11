from dataclasses import dataclass

import cv2
import numpy as np

ISO_ID1_WIDTH_MM = 85.60
ISO_ID1_HEIGHT_MM = 53.98
ISO_ID1_ASPECT = ISO_ID1_WIDTH_MM / ISO_ID1_HEIGHT_MM


@dataclass(frozen=True)
class Calibration:
    corners: np.ndarray
    pixels_per_mm: float
    corner_error_px: float


def _order_corners(points: np.ndarray) -> np.ndarray:
    ordered = np.zeros((4, 2), dtype=np.float32)
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).reshape(-1)
    ordered[0] = points[np.argmin(sums)]
    ordered[2] = points[np.argmax(sums)]
    ordered[1] = points[np.argmin(differences)]
    ordered[3] = points[np.argmax(differences)]
    return ordered


def detect_reference(rgb: np.ndarray) -> Calibration | None:
    """Find a prominent ISO ID-1 rectangle; uncertainty is conservative by design."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 140)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = rgb.shape[0] * rgb.shape[1]
    candidates: list[tuple[float, np.ndarray]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not 0.05 * image_area <= area <= 0.65 * image_area:
            continue
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue
        ordered = _order_corners(polygon.reshape(4, 2).astype(np.float32))
        top = np.linalg.norm(ordered[1] - ordered[0])
        bottom = np.linalg.norm(ordered[2] - ordered[3])
        left = np.linalg.norm(ordered[3] - ordered[0])
        right = np.linalg.norm(ordered[2] - ordered[1])
        width, height = (top + bottom) / 2, (left + right) / 2
        if height == 0:
            continue
        aspect = max(width, height) / min(width, height)
        aspect_error = abs(aspect - ISO_ID1_ASPECT) / ISO_ID1_ASPECT
        opposite_error = max(abs(top - bottom) / max(width, 1), abs(left - right) / max(height, 1))
        if aspect_error <= 0.12 and opposite_error <= 0.18:
            candidates.append((area, ordered))
    if not candidates:
        return None
    _, corners = max(candidates, key=lambda item: item[0])
    widths = [np.linalg.norm(corners[1] - corners[0]), np.linalg.norm(corners[2] - corners[3])]
    pixels_per_mm = float(np.mean(widths) / ISO_ID1_WIDTH_MM)
    corner_error = float(abs(widths[0] - widths[1]) / 2)
    return Calibration(corners=corners, pixels_per_mm=pixels_per_mm, corner_error_px=corner_error)


def blur_score(rgb: np.ndarray) -> float:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())
