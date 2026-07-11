import time
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from .calibration import Calibration
from .hand_geometry import expected_digits, extract_fingertip_crops
from .hand_landmarks import HandDetection
from .measurement import MeasurementConfidence, measure_projected_width
from .projection import project_crop_mask
from .quality import assess_nail_mask
from .schemas import CaptureType, NailMeasurement, QualityIssue, QualityIssueCode
from .segmentation import SegmentationResult
from .size_chart import recommend_size


class HandDetector(Protocol):
    def detect(self, rgb: NDArray[np.uint8]) -> HandDetection | None: ...


class Segmenter(Protocol):
    def segment(self, rgb: NDArray[np.uint8]) -> SegmentationResult: ...


@dataclass(frozen=True)
class PipelineResult:
    measurements: tuple[NailMeasurement, ...]
    issue: QualityIssue | None
    stage_timings_ms: dict[str, int]


def run_measurement_pipeline(
    rgb: NDArray[np.uint8],
    capture_type: CaptureType,
    calibration: Calibration,
    hand_detector: HandDetector,
    segmenter: Segmenter,
    *,
    segmentation_boundary_error_px: float,
) -> PipelineResult:
    if segmentation_boundary_error_px <= 0 or not np.isfinite(segmentation_boundary_error_px):
        raise ValueError("A validated positive segmentation boundary error is required")
    timings: dict[str, int] = {}

    started = time.perf_counter()
    detection = hand_detector.detect(rgb)
    timings["hand_landmarks"] = _elapsed_ms(started)
    if detection is None:
        return _retake(
            QualityIssueCode.WRONG_NAIL_COUNT,
            "The required nails could not be identified in this photo.",
            "Show only the requested hand with every required nail separated and visible.",
            timings,
        )

    started = time.perf_counter()
    try:
        crops = extract_fingertip_crops(rgb, detection.landmarks, capture_type)
    except ValueError:
        timings["crop_extraction"] = _elapsed_ms(started)
        return _retake(
            QualityIssueCode.WRONG_NAIL_COUNT,
            "The required nails could not be separated reliably.",
            "Flatten and separate the requested nails, then retake the photo.",
            timings,
        )
    timings["crop_extraction"] = _elapsed_ms(started)
    if tuple(crop.digit for crop in crops) != expected_digits(capture_type):
        return _retake(
            QualityIssueCode.WRONG_NAIL_COUNT,
            "The photo does not contain the expected nails.",
            "Retake the requested hand and include every named nail.",
            timings,
        )

    measurements: list[NailMeasurement] = []
    segmentation_elapsed = 0.0
    measurement_elapsed = 0.0
    for crop in crops:
        if crop.clipped:
            _record_model_timings(timings, segmentation_elapsed, measurement_elapsed)
            return _retake(
                QualityIssueCode.NAIL_CROPPED,
                "A nail edge is cut off by the image boundary.",
                "Retake with clear space around every requested nail.",
                timings,
            )
        segmentation_started = time.perf_counter()
        segmentation = segmenter.segment(crop.rgb)
        issues = assess_nail_mask(segmentation.mask, crop_clipped=crop.clipped)
        segmentation_elapsed += time.perf_counter() - segmentation_started
        if issues:
            _record_model_timings(timings, segmentation_elapsed, measurement_elapsed)
            return PipelineResult((), issues[0], timings)
        if segmentation.confidence < 0.75:
            _record_model_timings(timings, segmentation_elapsed, measurement_elapsed)
            return _retake(
                QualityIssueCode.LOW_CONFIDENCE,
                "The nail boundary is not confident enough to measure.",
                "Use bright even light, separate the nails, and retake the photo.",
                timings,
            )

        measurement_started = time.perf_counter()
        try:
            projected_mask = project_crop_mask(
                segmentation.mask,
                crop,
                rgb.shape[:2],
                calibration,
            )
            projected_width = measure_projected_width(
                projected_mask.mask,
                calibration,
                segmentation_boundary_error_px=(
                    segmentation_boundary_error_px * projected_mask.boundary_scale
                ),
                segmentation_confidence=segmentation.confidence,
            )
        except ValueError:
            measurement_elapsed += time.perf_counter() - measurement_started
            _record_model_timings(timings, segmentation_elapsed, measurement_elapsed)
            return _retake(
                QualityIssueCode.LOW_CONFIDENCE,
                "The nail boundary could not be calibrated reliably.",
                "Keep the card and nails flat and fully visible, then retake the photo.",
                timings,
            )
        measurement_elapsed += time.perf_counter() - measurement_started
        if projected_width.confidence == MeasurementConfidence.LOW:
            _record_model_timings(timings, segmentation_elapsed, measurement_elapsed)
            return _retake(
                QualityIssueCode.LOW_CONFIDENCE,
                "Measurement uncertainty is too high for a safe size recommendation.",
                "Retake directly above the flat card and nails with sharper lighting.",
                timings,
            )
        recommendation = recommend_size(projected_width.width_mm, projected_width.uncertainty_mm)
        if recommendation is None:
            _record_model_timings(timings, segmentation_elapsed, measurement_elapsed)
            return _retake(
                QualityIssueCode.OUTSIDE_DEFAULT_CHART,
                "This nail falls outside the supported default tip chart.",
                "Ask the nail artist to measure this nail manually or use a wider chart.",
                timings,
            )
        measurements.append(
            NailMeasurement(
                digit=crop.digit,
                projected_width_mm=projected_width.width_mm,
                uncertainty_mm=projected_width.uncertainty_mm,
                recommended_size=recommendation.recommended_size,
                alternate_size=recommendation.alternate_size,
                confidence=projected_width.confidence.value,
                contour=list(projected_mask.source_contour),
            )
        )

    _record_model_timings(timings, segmentation_elapsed, measurement_elapsed)
    return PipelineResult(tuple(measurements), None, timings)


def _retake(
    code: QualityIssueCode,
    message: str,
    correction: str,
    timings: dict[str, int],
) -> PipelineResult:
    return PipelineResult(
        (),
        QualityIssue(code=code, message=message, correction=correction),
        timings,
    )


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1_000)


def _record_model_timings(
    timings: dict[str, int], segmentation_elapsed: float, measurement_elapsed: float
) -> None:
    timings["segmentation"] = round(segmentation_elapsed * 1_000)
    timings["calibrated_measurement"] = round(measurement_elapsed * 1_000)
