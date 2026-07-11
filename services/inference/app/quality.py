from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from .calibration import Calibration, ReferenceFailure, analyze_reference, blur_score
from .schemas import QualityIssue, QualityIssueCode


@dataclass(frozen=True)
class CaptureQuality:
    calibration: Calibration | None
    issues: tuple[QualityIssue, ...]


def _issue(code: QualityIssueCode, message: str, correction: str) -> QualityIssue:
    return QualityIssue(code=code, message=message, correction=correction)


def glare_fraction(rgb: NDArray[np.uint8]) -> float:
    """Detect localized clipped highlights while ignoring a uniform white backdrop."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    highlight = (gray >= 250).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(highlight, connectivity=8)
    image_area = gray.size
    localized_area = sum(
        int(stats[index, cv2.CC_STAT_AREA])
        for index in range(1, count)
        if 0.001 * image_area <= stats[index, cv2.CC_STAT_AREA] <= 0.12 * image_area
    )
    return localized_area / image_area


def assess_capture(rgb: NDArray[np.uint8]) -> CaptureQuality:
    if blur_score(rgb) < 60:
        return CaptureQuality(
            None,
            (
                _issue(
                    QualityIssueCode.BLUR,
                    "The photo is too blurry to measure.",
                    "Steady the phone, add light, and retake the photo.",
                ),
            ),
        )
    if glare_fraction(rgb) > 0.015:
        return CaptureQuality(
            None,
            (
                _issue(
                    QualityIssueCode.GLARE,
                    "Bright glare obscures part of the capture.",
                    "Move away from direct light and retake with soft, even lighting.",
                ),
            ),
        )

    reference = analyze_reference(rgb)
    if reference.calibration is not None:
        return CaptureQuality(reference.calibration, ())
    if reference.failure == ReferenceFailure.ANGLE_TOO_STEEP:
        issue = _issue(
            QualityIssueCode.ANGLE_TOO_STEEP,
            "The card and hand are viewed at too steep an angle.",
            "Hold the camera directly above the flat card and nails.",
        )
    elif reference.failure in {
        ReferenceFailure.INVALID,
        ReferenceFailure.CROPPED,
        ReferenceFailure.UNCERTAIN,
    }:
        issue = _issue(
            QualityIssueCode.REFERENCE_INVALID,
            "The reference card geometry is incomplete or uncertain.",
            "Show all four card corners and keep the entire card flat in the frame.",
        )
    else:
        issue = _issue(
            QualityIssueCode.REFERENCE_MISSING,
            "The reference card could not be found.",
            "Place a blank ISO ID-1 size card flat beside your nails.",
        )
    return CaptureQuality(None, (issue,))


def assess_nail_mask(
    mask: NDArray[np.uint8],
    *,
    minimum_pixels: int = 500,
) -> tuple[QualityIssue, ...]:
    binary = (mask > 0).astype(np.uint8)
    pixel_count = int(binary.sum())
    if pixel_count < minimum_pixels:
        return (
            _issue(
                QualityIssueCode.LOW_CONFIDENCE,
                "The visible nail area is too small to measure reliably.",
                "Move the camera closer while keeping the card and nail fully visible.",
            ),
        )
    border_pixels = np.concatenate([binary[0, :], binary[-1, :], binary[:, 0], binary[:, -1]])
    if border_pixels.any():
        return (
            _issue(
                QualityIssueCode.NAIL_CROPPED,
                "A nail edge is cut off by the image or crop boundary.",
                "Retake with clear space around every nail edge.",
            ),
        )
    return ()
