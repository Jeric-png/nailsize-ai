import argparse
import json
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

CHART_ID = "platform-default"
CHART_VERSION = "1"
CHART_WIDTHS_MM = tuple(float(18 - size) for size in range(10))
CALIBRATION_METRICS = (
    "exact_size_rate",
    "exact_or_adjacent_rate",
    "more_than_one_size_miss_rate",
    "unmappable_rate",
    "mean_best_fit_tip_margin_mm",
    "p90_absolute_best_fit_tip_margin_mm",
)


@dataclass(frozen=True)
class SizeCalibrationObservation:
    participant_id: str
    nail_id: str
    physical_width_mm: float
    physical_best_fit_size: int
    curvature_cohort: str


@dataclass(frozen=True)
class CurvatureReview:
    cohort: str
    review_ref: str


@dataclass(frozen=True)
class SizeCalibrationMetrics:
    exact_size_rate: float
    exact_or_adjacent_rate: float
    more_than_one_size_miss_rate: float
    unmappable_rate: float
    mean_best_fit_tip_margin_mm: float
    p90_absolute_best_fit_tip_margin_mm: float


def build_size_calibration_report(
    observations: Sequence[SizeCalibrationObservation],
    curvature_reviews: Sequence[CurvatureReview],
    *,
    dataset_version: str,
    calibration_review_ref: str,
    bootstrap_iterations: int = 2_000,
    seed: int = 20260712,
    minimum_participants: int = 200,
    minimum_nails: int = 2_000,
) -> dict[str, Any]:
    records = _validate_observations(observations)
    reviews = _validate_reviews(curvature_reviews, records)
    if (
        not isinstance(dataset_version, str)
        or not dataset_version.strip()
        or not isinstance(calibration_review_ref, str)
        or not calibration_review_ref.strip()
    ):
        raise ValueError("Dataset version and calibration review reference are required")
    if (
        isinstance(minimum_participants, bool)
        or not isinstance(minimum_participants, int)
        or minimum_participants <= 0
        or isinstance(minimum_nails, bool)
        or not isinstance(minimum_nails, int)
        or minimum_nails <= 0
    ):
        raise ValueError("Minimum participant and nail counts must be positive integers")
    dataset_version = dataset_version.strip()
    calibration_review_ref = calibration_review_ref.strip()

    metrics = _metrics(records)
    participant_count = len({item.participant_id for item in records})
    dataset_checks = {
        "minimum_participants": participant_count >= minimum_participants,
        "minimum_nails": len(records) >= minimum_nails,
        "all_widths_mappable": metrics.unmappable_rate == 0,
        "curvature_reviews_present": bool(reviews),
    }
    gate_checks = {
        "exact_size_rate": metrics.exact_size_rate >= 0.90,
        "exact_or_adjacent_rate": metrics.exact_or_adjacent_rate >= 0.99,
        "more_than_one_size_miss_rate": metrics.more_than_one_size_miss_rate <= 0.01,
        "calibration_review_present": bool(calibration_review_ref.strip()),
    }
    cohort_results = _cohort_results(records, reviews, metrics)
    return {
        "schema_version": "nailsize-size-calibration-report@1",
        "dataset_version": dataset_version,
        "chart_id": CHART_ID,
        "chart_version": CHART_VERSION,
        "participant_count": participant_count,
        "nail_count": len(records),
        "metrics": asdict(metrics),
        "confidence_intervals_95": _clustered_intervals(
            records, iterations=bootstrap_iterations, seed=seed
        ),
        "dataset_checks": dataset_checks,
        "gate_checks": gate_checks,
        "adequately_sampled_curvature_cohorts": cohort_results,
        "calibration_review_ref": calibration_review_ref,
        "passed": (
            all(dataset_checks.values())
            and all(gate_checks.values())
            and all(item["passed"] for item in cohort_results)
        ),
    }


def load_observations(path: Path) -> list[SizeCalibrationObservation]:
    observations: list[SizeCalibrationObservation] = []
    try:
        with path.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    if not isinstance(payload, dict) or set(payload) != {
                        "participant_id",
                        "nail_id",
                        "physical_width_mm",
                        "physical_best_fit_size",
                        "curvature_cohort",
                    }:
                        raise TypeError
                    observations.append(SizeCalibrationObservation(**payload))
                except (json.JSONDecodeError, TypeError) as error:
                    raise ValueError(
                        f"Invalid size-calibration observation on line {line_number}"
                    ) from error
    except OSError as error:
        raise ValueError("Size-calibration observations could not be read") from error
    return _validate_observations(observations)


def _recommend_size(width_mm: float) -> int | None:
    if width_mm > CHART_WIDTHS_MM[0] or width_mm < CHART_WIDTHS_MM[-1]:
        return None
    return next(
        size
        for size, tip_width in enumerate(CHART_WIDTHS_MM)
        if tip_width >= width_mm
        and (size == len(CHART_WIDTHS_MM) - 1 or CHART_WIDTHS_MM[size + 1] < width_mm)
    )


def _metrics(observations: Sequence[SizeCalibrationObservation]) -> SizeCalibrationMetrics:
    predictions = [_recommend_size(item.physical_width_mm) for item in observations]
    exact = [
        prediction == item.physical_best_fit_size
        for prediction, item in zip(predictions, observations, strict=True)
    ]
    adjacent = [
        prediction is not None and abs(prediction - item.physical_best_fit_size) <= 1
        for prediction, item in zip(predictions, observations, strict=True)
    ]
    severe = [
        prediction is None or abs(prediction - item.physical_best_fit_size) > 1
        for prediction, item in zip(predictions, observations, strict=True)
    ]
    margins = np.asarray(
        [
            CHART_WIDTHS_MM[item.physical_best_fit_size] - item.physical_width_mm
            for item in observations
        ],
        dtype=float,
    )
    return SizeCalibrationMetrics(
        exact_size_rate=float(np.mean(exact)),
        exact_or_adjacent_rate=float(np.mean(adjacent)),
        more_than_one_size_miss_rate=float(np.mean(severe)),
        unmappable_rate=float(np.mean([prediction is None for prediction in predictions])),
        mean_best_fit_tip_margin_mm=float(np.mean(margins)),
        p90_absolute_best_fit_tip_margin_mm=float(np.quantile(np.abs(margins), 0.90)),
    )


def _cohort_results(
    observations: Sequence[SizeCalibrationObservation],
    reviews: Sequence[CurvatureReview],
    overall: SizeCalibrationMetrics,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for review in sorted(reviews, key=lambda item: item.cohort):
        cohort = [item for item in observations if item.curvature_cohort == review.cohort]
        metrics = _metrics(cohort)
        checks = {
            "exact_size_rate_gap": metrics.exact_size_rate >= overall.exact_size_rate - 0.05,
            "review_present": bool(review.review_ref.strip()),
        }
        results.append(
            {
                "cohort": review.cohort,
                "participant_count": len({item.participant_id for item in cohort}),
                "nail_count": len(cohort),
                "metrics": asdict(metrics),
                "checks": checks,
                "review_ref": review.review_ref,
                "passed": all(checks.values()),
            }
        )
    return results


def _clustered_intervals(
    observations: Sequence[SizeCalibrationObservation], *, iterations: int, seed: int
) -> dict[str, dict[str, float]]:
    if iterations < 100:
        raise ValueError("At least 100 bootstrap iterations are required")
    by_participant: dict[str, list[SizeCalibrationObservation]] = defaultdict(list)
    for item in observations:
        by_participant[item.participant_id].append(item)
    participant_ids = sorted(by_participant)
    random = np.random.default_rng(seed)
    samples = {name: np.empty(iterations, dtype=float) for name in CALIBRATION_METRICS}
    for index in range(iterations):
        chosen = random.choice(participant_ids, size=len(participant_ids), replace=True)
        sampled = [
            record for participant_id in chosen for record in by_participant[str(participant_id)]
        ]
        metrics = _metrics(sampled)
        for name in CALIBRATION_METRICS:
            samples[name][index] = getattr(metrics, name)
    return {
        name: {
            "lower": float(np.quantile(values, 0.025)),
            "upper": float(np.quantile(values, 0.975)),
        }
        for name, values in samples.items()
    }


def _validate_observations(
    observations: Sequence[SizeCalibrationObservation],
) -> list[SizeCalibrationObservation]:
    records = list(observations)
    if not records:
        raise ValueError("At least one size-calibration observation is required")
    seen: set[tuple[str, str]] = set()
    for item in records:
        if (
            not isinstance(item, SizeCalibrationObservation)
            or not isinstance(item.participant_id, str)
            or not item.participant_id.strip()
            or item.participant_id != item.participant_id.strip()
            or not isinstance(item.nail_id, str)
            or not item.nail_id.strip()
            or item.nail_id != item.nail_id.strip()
            or isinstance(item.physical_width_mm, bool)
            or not isinstance(item.physical_width_mm, (int, float))
            or not math.isfinite(item.physical_width_mm)
            or item.physical_width_mm <= 0
            or isinstance(item.physical_best_fit_size, bool)
            or not isinstance(item.physical_best_fit_size, int)
            or not 0 <= item.physical_best_fit_size <= 9
            or not isinstance(item.curvature_cohort, str)
            or not item.curvature_cohort.strip()
            or item.curvature_cohort != item.curvature_cohort.strip()
        ):
            raise ValueError("Size-calibration observations must be unique and well formed")
        key = (item.participant_id, item.nail_id)
        if key in seen:
            raise ValueError("Size-calibration observations must be unique and well formed")
        seen.add(key)
    return records


def _validate_reviews(
    reviews: Sequence[CurvatureReview], observations: Sequence[SizeCalibrationObservation]
) -> list[CurvatureReview]:
    records = list(reviews)
    cohorts = {item.curvature_cohort for item in observations}
    if (
        not records
        or len({item.cohort for item in records}) != len(records)
        or any(
            not isinstance(item, CurvatureReview)
            or not isinstance(item.cohort, str)
            or not item.cohort.strip()
            or item.cohort != item.cohort.strip()
            or item.cohort not in cohorts
            or not isinstance(item.review_ref, str)
            or not item.review_ref.strip()
            or item.review_ref != item.review_ref.strip()
            for item in records
        )
    ):
        raise ValueError("Curvature reviews must be unique, populated, and present in the dataset")
    return records


def _curvature_review(value: str) -> CurvatureReview:
    cohort, separator, review_ref = value.partition("=")
    cohort = cohort.strip()
    review_ref = review_ref.strip()
    if not separator or not cohort or not review_ref:
        raise argparse.ArgumentTypeError("Curvature reviews must use cohort=review-reference")
    return CurvatureReview(cohort, review_ref)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a physical best-fit size calibration report"
    )
    parser.add_argument("observations", type=Path)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--calibration-review-ref", required=True)
    parser.add_argument(
        "--curvature-review",
        action="append",
        default=[],
        type=_curvature_review,
        help="Reviewer-approved adequate cohort as cohort=review-reference",
    )
    parser.add_argument("--bootstrap-iterations", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = build_size_calibration_report(
        load_observations(arguments.observations),
        arguments.curvature_review,
        dataset_version=arguments.dataset_version,
        calibration_review_ref=arguments.calibration_review_ref,
        bootstrap_iterations=arguments.bootstrap_iterations,
        seed=arguments.seed,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
