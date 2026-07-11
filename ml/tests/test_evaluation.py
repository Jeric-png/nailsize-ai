import numpy as np
import pytest

from nailsize_ml.evaluation import (
    evaluate_release_gates,
    measurement_metrics,
    segmentation_metrics,
)


def test_segmentation_reports_overlap_and_boundary_error() -> None:
    expected = np.zeros((20, 20), dtype=np.uint8)
    predicted = np.zeros_like(expected)
    expected[5:15, 5:15] = 1
    predicted[5:15, 6:16] = 1
    metrics = segmentation_metrics(predicted, expected)
    assert metrics.iou == pytest.approx(90 / 110)
    assert metrics.dice == pytest.approx(0.9)
    assert 0 < metrics.mean_boundary_error_px < 1
    assert metrics.p95_boundary_error_px == pytest.approx(1.0)


def test_segmentation_handles_paired_empty_masks_and_rejects_one_sided_empty() -> None:
    empty = np.zeros((10, 10), dtype=np.uint8)
    paired = segmentation_metrics(empty, empty)
    assert paired.iou == 1.0
    assert paired.dice == 1.0
    assert paired.mean_boundary_error_px == 0.0

    nonempty = empty.copy()
    nonempty[4:6, 4:6] = 1
    one_sided = segmentation_metrics(nonempty, empty)
    assert np.isinf(one_sided.mean_boundary_error_px)


def test_measurement_metrics_match_release_definitions() -> None:
    metrics = measurement_metrics(
        np.array([10.0, 11.2, 12.4, 13.6]),
        np.array([10.1, 11.0, 12.0, 14.0]),
        np.array([9, 8, 7, 4]),
        np.array([9, 7, 6, 6]),
    )
    assert metrics.nail_count == 4
    assert metrics.width_mae_mm == pytest.approx(0.275)
    assert metrics.width_p90_error_mm == pytest.approx(0.4)
    assert metrics.signed_bias_mm == pytest.approx(0.025)
    assert metrics.exact_size_rate == 0.25
    assert metrics.exact_or_adjacent_rate == 0.75
    assert metrics.more_than_one_size_miss_rate == 0.25


def test_release_gate_requires_every_documented_measurement_threshold() -> None:
    passing = measurement_metrics(
        np.full(100, 12.1),
        np.full(100, 12.0),
        np.concatenate((np.zeros(99, dtype=int), np.ones(1, dtype=int))),
        np.zeros(100, dtype=int),
    )
    result = evaluate_release_gates(passing)
    assert result.passed
    assert all(result.checks.values())

    failing = measurement_metrics(
        np.full(100, 13.0),
        np.full(100, 12.0),
        np.full(100, 3, dtype=int),
        np.zeros(100, dtype=int),
    )
    result = evaluate_release_gates(failing)
    assert not result.passed
    assert not result.checks["width_mae_mm"]
    assert not result.checks["more_than_one_size_miss_rate"]


@pytest.mark.parametrize(
    "call",
    [
        lambda: segmentation_metrics(np.zeros((0, 1)), np.zeros((0, 1))),
        lambda: segmentation_metrics(np.zeros((2, 2)), np.zeros((3, 3))),
        lambda: measurement_metrics(np.array([1.0]), np.array([]), np.array([1]), np.array([1])),
        lambda: measurement_metrics(
            np.array([np.nan]), np.array([1.0]), np.array([1]), np.array([1])
        ),
        lambda: measurement_metrics(
            np.array([-1.0]), np.array([1.0]), np.array([1]), np.array([1])
        ),
        lambda: measurement_metrics(
            np.array([1.0]), np.array([1.0]), np.array([1.5]), np.array([1])
        ),
    ],
)
def test_rejects_invalid_evaluation_inputs(call) -> None:
    with pytest.raises(ValueError):
        call()
