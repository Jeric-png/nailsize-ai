from dataclasses import dataclass
from enum import StrEnum

import cv2
import numpy as np
from numpy.typing import NDArray

from .calibration import Calibration, propagate_width_uncertainty


@dataclass(frozen=True)
class ChordMeasurement:
    width_px: float
    start: tuple[float, float]
    end: tuple[float, float]
    longitudinal_axis: tuple[float, float]


class MeasurementConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class ProjectedWidth:
    width_mm: float
    uncertainty_mm: float
    confidence: MeasurementConfidence
    chord: ChordMeasurement


def measure_maximum_transverse_chord(mask: NDArray[np.uint8]) -> ChordMeasurement:
    """Measure the widest mask chord perpendicular to its PCA longitudinal axis."""
    binary = (mask > 0).astype(np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        raise ValueError("Mask has no measurable contour")
    contour = max(contours, key=cv2.contourArea).reshape(-1, 2).astype(np.float64)
    if len(contour) < 12 or cv2.contourArea(contour.astype(np.float32)) < 20:
        raise ValueError("Mask contour is too small")

    center = contour.mean(axis=0)
    covariance = np.cov((contour - center).T)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    longitudinal = eigenvectors[:, int(np.argmax(eigenvalues))]
    transverse = np.array([-longitudinal[1], longitudinal[0]])
    if longitudinal[1] < 0:
        longitudinal = -longitudinal
        transverse = -transverse

    relative = contour - center
    along = relative @ longitudinal
    across = relative @ transverse
    minimum_along, maximum_along = float(along.min()), float(along.max())
    usable_min = minimum_along + 0.10 * (maximum_along - minimum_along)
    usable_max = maximum_along - 0.10 * (maximum_along - minimum_along)

    best_width = 0.0
    best_along = 0.0
    best_low = 0.0
    best_high = 0.0
    for position in np.arange(np.ceil(usable_min), np.floor(usable_max) + 1):
        selected = across[np.abs(along - position) <= 0.75]
        if len(selected) < 2:
            continue
        low, high = float(selected.min()), float(selected.max())
        width = high - low
        if width > best_width:
            best_width, best_along, best_low, best_high = width, float(position), low, high
    if best_width <= 0:
        raise ValueError("Mask has no valid transverse chord")

    start = center + best_along * longitudinal + best_low * transverse
    end = center + best_along * longitudinal + best_high * transverse
    return ChordMeasurement(
        width_px=best_width,
        start=(float(start[0]), float(start[1])),
        end=(float(end[0]), float(end[1])),
        longitudinal_axis=(float(longitudinal[0]), float(longitudinal[1])),
    )


def score_measurement_confidence(
    uncertainty_mm: float, segmentation_confidence: float
) -> MeasurementConfidence:
    if uncertainty_mm < 0 or not 0 <= segmentation_confidence <= 1:
        raise ValueError("Uncertainty and segmentation confidence are out of range")
    if uncertainty_mm <= 0.4 and segmentation_confidence >= 0.90:
        return MeasurementConfidence.HIGH
    if uncertainty_mm <= 0.7 and segmentation_confidence >= 0.75:
        return MeasurementConfidence.MEDIUM
    return MeasurementConfidence.LOW


def measure_projected_width(
    rectified_mask: NDArray[np.uint8],
    calibration: Calibration,
    *,
    segmentation_boundary_error_px: float,
    segmentation_confidence: float,
) -> ProjectedWidth:
    """Create a calibrated projected width; a Calibration object is mandatory by type."""
    chord = measure_maximum_transverse_chord(rectified_mask)
    width_mm = chord.width_px / calibration.pixels_per_mm
    uncertainty_mm = propagate_width_uncertainty(
        chord.width_px,
        calibration,
        segmentation_boundary_error_px,
    )
    return ProjectedWidth(
        width_mm=width_mm,
        uncertainty_mm=uncertainty_mm,
        confidence=score_measurement_confidence(uncertainty_mm, segmentation_confidence),
        chord=chord,
    )
