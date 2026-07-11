import argparse
import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .evaluation import MeasurementMetrics, evaluate_release_gates, measurement_metrics


@dataclass(frozen=True)
class AccuracyObservation:
    participant_id: str
    predicted_width_mm: float
    ground_truth_width_mm: float
    predicted_size: int
    ground_truth_size: int
    cohorts: dict[str, str]


METRIC_NAMES = (
    "width_mae_mm",
    "width_p90_error_mm",
    "signed_bias_mm",
    "exact_size_rate",
    "exact_or_adjacent_rate",
    "more_than_one_size_miss_rate",
)
REQUIRED_COHORT_DIMENSIONS = frozenset({"skin_tone", "curvature", "width", "device"})


def build_accuracy_report(
    observations: Sequence[AccuracyObservation],
    adequately_sampled_cohorts: Iterable[tuple[str, str]],
    *,
    bootstrap_iterations: int = 2_000,
    seed: int = 20260712,
    minimum_participants: int = 200,
    minimum_nails: int = 2_000,
) -> dict[str, Any]:
    records = _validated_observations(observations)
    overall = _metrics(records)
    overall_gates = evaluate_release_gates(overall)
    confidence_intervals = participant_clustered_confidence_intervals(
        records, iterations=bootstrap_iterations, seed=seed
    )

    requested_cohorts = list(adequately_sampled_cohorts)
    if len(set(requested_cohorts)) != len(requested_cohorts):
        raise ValueError("Adequately sampled cohorts must be unique")

    cohort_results: list[dict[str, Any]] = []
    for dimension, value in sorted(requested_cohorts):
        if not dimension or not value:
            raise ValueError("Cohort dimension and value must be non-empty")
        cohort_records = [item for item in records if item.cohorts.get(dimension) == value]
        if not cohort_records:
            raise ValueError(f"Declared adequate cohort has no observations: {dimension}={value}")
        cohort_metrics = _metrics(cohort_records)
        cohort_participants = len({item.participant_id for item in cohort_records})
        checks = {
            "width_mae_mm": cohort_metrics.width_mae_mm <= 0.85,
            "exact_size_rate_gap": (
                cohort_metrics.exact_size_rate >= overall.exact_size_rate - 0.05
            ),
        }
        cohort_results.append(
            {
                "dimension": dimension,
                "value": value,
                "participant_count": cohort_participants,
                "nail_count": len(cohort_records),
                "metrics": asdict(cohort_metrics),
                "checks": checks,
                "passed": all(checks.values()),
            }
        )

    participant_count = len({item.participant_id for item in records})
    dataset_checks = {
        "minimum_participants": participant_count >= minimum_participants,
        "minimum_nails": len(records) >= minimum_nails,
        "required_cohort_dimensions": REQUIRED_COHORT_DIMENSIONS.issubset(
            {dimension for dimension, _ in requested_cohorts}
        ),
    }
    return {
        "schema_version": "nailsize-accuracy-report@1",
        "participant_count": participant_count,
        "nail_count": len(records),
        "dataset_checks": dataset_checks,
        "overall": {
            "metrics": asdict(overall),
            "confidence_intervals_95": confidence_intervals,
            "checks": overall_gates.checks,
            "passed": overall_gates.passed,
        },
        "adequately_sampled_cohorts": cohort_results,
        "passed": (
            all(dataset_checks.values())
            and overall_gates.passed
            and all(item["passed"] for item in cohort_results)
        ),
    }


def participant_clustered_confidence_intervals(
    observations: Sequence[AccuracyObservation], *, iterations: int, seed: int
) -> dict[str, dict[str, float]]:
    records = _validated_observations(observations)
    if iterations < 100:
        raise ValueError("At least 100 bootstrap iterations are required")
    by_participant: dict[str, list[AccuracyObservation]] = defaultdict(list)
    for item in records:
        by_participant[item.participant_id].append(item)
    participant_ids = sorted(by_participant)
    random = np.random.default_rng(seed)
    samples = {name: np.empty(iterations, dtype=float) for name in METRIC_NAMES}
    for index in range(iterations):
        chosen = random.choice(participant_ids, size=len(participant_ids), replace=True)
        bootstrap_records = [record for key in chosen for record in by_participant[str(key)]]
        metrics = _metrics(bootstrap_records)
        for name in METRIC_NAMES:
            samples[name][index] = getattr(metrics, name)
    return {
        name: {
            "lower": float(np.quantile(values, 0.025)),
            "upper": float(np.quantile(values, 0.975)),
        }
        for name, values in samples.items()
    }


def load_observations(path: Path) -> list[AccuracyObservation]:
    observations: list[AccuracyObservation] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                observations.append(AccuracyObservation(**payload))
            except (json.JSONDecodeError, TypeError) as error:
                raise ValueError(f"Invalid observation on line {line_number}") from error
    return _validated_observations(observations)


def _metrics(observations: Sequence[AccuracyObservation]) -> MeasurementMetrics:
    return measurement_metrics(
        np.asarray([item.predicted_width_mm for item in observations]),
        np.asarray([item.ground_truth_width_mm for item in observations]),
        np.asarray([item.predicted_size for item in observations], dtype=np.int64),
        np.asarray([item.ground_truth_size for item in observations], dtype=np.int64),
    )


def _validated_observations(
    observations: Sequence[AccuracyObservation],
) -> list[AccuracyObservation]:
    records = list(observations)
    if not records:
        raise ValueError("At least one accuracy observation is required")
    for item in records:
        if not item.participant_id.strip():
            raise ValueError("Participant IDs must be non-empty")
        if not isinstance(item.cohorts, dict) or any(
            not isinstance(key, str) or not key or not isinstance(value, str) or not value
            for key, value in item.cohorts.items()
        ):
            raise ValueError("Cohorts must map non-empty strings to non-empty strings")
    _metrics(records)
    return records


def _cohort(value: str) -> tuple[str, str]:
    dimension, separator, cohort_value = value.partition("=")
    if not separator or not dimension or not cohort_value:
        raise argparse.ArgumentTypeError("Cohorts must use dimension=value")
    return dimension, cohort_value


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a fail-closed accuracy release report")
    parser.add_argument("observations", type=Path, help="Participant-disjoint JSONL observations")
    parser.add_argument(
        "--adequate-cohort",
        action="append",
        default=[],
        type=_cohort,
        help="Reviewer-approved adequately sampled cohort as dimension=value",
    )
    parser.add_argument("--bootstrap-iterations", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = build_accuracy_report(
        load_observations(arguments.observations),
        arguments.adequate_cohort,
        bootstrap_iterations=arguments.bootstrap_iterations,
        seed=arguments.seed,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
