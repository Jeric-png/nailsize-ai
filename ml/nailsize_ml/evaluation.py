from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class SegmentationMetrics:
    iou: float
    dice: float
    mean_boundary_error_px: float
    p95_boundary_error_px: float


@dataclass(frozen=True)
class MeasurementMetrics:
    nail_count: int
    width_mae_mm: float
    width_p90_error_mm: float
    signed_bias_mm: float
    exact_size_rate: float
    exact_or_adjacent_rate: float
    more_than_one_size_miss_rate: float


@dataclass(frozen=True)
class ReleaseGateResult:
    passed: bool
    checks: dict[str, bool]


def segmentation_metrics(
    prediction: NDArray[np.uint8], ground_truth: NDArray[np.uint8]
) -> SegmentationMetrics:
    predicted = _binary_mask(prediction)
    expected = _binary_mask(ground_truth)
    if predicted.shape != expected.shape:
        raise ValueError("Prediction and ground-truth masks must have identical shapes")

    intersection = int(np.logical_and(predicted, expected).sum())
    union = int(np.logical_or(predicted, expected).sum())
    total = int(predicted.sum() + expected.sum())
    iou = 1.0 if union == 0 else intersection / union
    dice = 1.0 if total == 0 else 2 * intersection / total

    predicted_boundary = _boundary_points(predicted)
    expected_boundary = _boundary_points(expected)
    if len(predicted_boundary) == 0 and len(expected_boundary) == 0:
        distances = np.zeros(1, dtype=float)
    elif len(predicted_boundary) == 0 or len(expected_boundary) == 0:
        distances = np.full(1, np.inf, dtype=float)
    else:
        pairwise = np.linalg.norm(
            predicted_boundary[:, None, :] - expected_boundary[None, :, :], axis=2
        )
        distances = np.concatenate((pairwise.min(axis=1), pairwise.min(axis=0)))

    boundary_mean = float(distances.mean())
    boundary_p95 = (
        float("inf") if np.isinf(distances).any() else float(np.quantile(distances, 0.95))
    )
    return SegmentationMetrics(
        iou=float(iou),
        dice=float(dice),
        mean_boundary_error_px=boundary_mean,
        p95_boundary_error_px=boundary_p95,
    )


def measurement_metrics(
    predicted_widths_mm: NDArray[np.floating[Any]],
    ground_truth_widths_mm: NDArray[np.floating[Any]],
    predicted_sizes: NDArray[np.integer[Any]],
    ground_truth_sizes: NDArray[np.integer[Any]],
) -> MeasurementMetrics:
    predicted_widths = _finite_vector(predicted_widths_mm, "predicted widths")
    ground_truth_widths = _finite_vector(ground_truth_widths_mm, "ground-truth widths")
    predicted_size_values = _integer_vector(predicted_sizes, "predicted sizes")
    ground_truth_size_values = _integer_vector(ground_truth_sizes, "ground-truth sizes")
    lengths = {
        len(predicted_widths),
        len(ground_truth_widths),
        len(predicted_size_values),
        len(ground_truth_size_values),
    }
    if len(lengths) != 1 or not predicted_widths.size:
        raise ValueError("Paired non-empty width and size vectors are required")
    if np.any(predicted_widths <= 0) or np.any(ground_truth_widths <= 0):
        raise ValueError("Widths must be positive")

    width_errors = predicted_widths - ground_truth_widths
    absolute_width_errors = np.abs(width_errors)
    size_errors = np.abs(predicted_size_values - ground_truth_size_values)
    return MeasurementMetrics(
        nail_count=len(predicted_widths),
        width_mae_mm=float(absolute_width_errors.mean()),
        width_p90_error_mm=float(np.quantile(absolute_width_errors, 0.90)),
        signed_bias_mm=float(width_errors.mean()),
        exact_size_rate=float((size_errors == 0).mean()),
        exact_or_adjacent_rate=float((size_errors <= 1).mean()),
        more_than_one_size_miss_rate=float((size_errors > 1).mean()),
    )


def evaluate_release_gates(metrics: MeasurementMetrics) -> ReleaseGateResult:
    checks = {
        "width_mae_mm": metrics.width_mae_mm <= 0.6,
        "width_p90_error_mm": metrics.width_p90_error_mm <= 1.0,
        "signed_bias_mm": abs(metrics.signed_bias_mm) <= 0.2,
        "exact_size_rate": metrics.exact_size_rate >= 0.90,
        "exact_or_adjacent_rate": metrics.exact_or_adjacent_rate >= 0.99,
        "more_than_one_size_miss_rate": metrics.more_than_one_size_miss_rate <= 0.01,
    }
    return ReleaseGateResult(passed=all(checks.values()), checks=checks)


def _binary_mask(mask: NDArray[np.uint8]) -> NDArray[np.bool_]:
    array = np.asarray(mask)
    if array.ndim != 2 or array.size == 0:
        raise ValueError("Masks must be non-empty two-dimensional arrays")
    return array > 0


def _boundary_points(mask: NDArray[np.bool_]) -> NDArray[np.float64]:
    padded = np.pad(mask, 1, mode="constant", constant_values=False)
    interior = mask.copy()
    for row_offset, column_offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        interior &= padded[
            1 + row_offset : 1 + row_offset + mask.shape[0],
            1 + column_offset : 1 + column_offset + mask.shape[1],
        ]
    return np.argwhere(mask & ~interior).astype(float)


def _finite_vector(values: NDArray[np.floating[Any]], label: str) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or not np.isfinite(array).all():
        raise ValueError(f"{label.capitalize()} must be a finite one-dimensional vector")
    return array


def _integer_vector(values: NDArray[np.integer[Any]], label: str) -> NDArray[np.int64]:
    array = np.asarray(values)
    if array.ndim != 1 or not np.issubdtype(array.dtype, np.integer):
        raise ValueError(f"{label.capitalize()} must be a one-dimensional integer vector")
    return array.astype(np.int64)
