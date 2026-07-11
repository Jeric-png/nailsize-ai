import argparse
import json
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .reporting import REQUIRED_COHORT_DIMENSIONS

EXPECTED_NAILS = frozenset(
    f"{side}_{digit}"
    for side in ("left", "right")
    for digit in ("thumb", "index", "middle", "ring", "pinky")
)
OPERATIONAL_METRICS = (
    "first_pass_completion_rate",
    "after_one_retake_completion_rate",
    "invalid_false_acceptance_rate",
    "valid_false_rejection_rate",
    "repeatability_mean_absolute_difference_mm",
    "repeatability_p90_absolute_difference_mm",
    "repeatability_signed_difference_mm",
)


@dataclass(frozen=True)
class SessionOutcome:
    participant_id: str
    attempts_complete: tuple[bool, ...]


@dataclass(frozen=True)
class QualityDecision:
    participant_id: str
    ground_truth_valid: bool
    system_accepted: bool
    cohorts: dict[str, str]


@dataclass(frozen=True)
class RepeatabilityObservation:
    participant_id: str
    repetition_id: str
    widths_mm: dict[str, float]


@dataclass(frozen=True)
class CohortReview:
    dimension: str
    value: str
    parity_review_ref: str


@dataclass(frozen=True)
class OperationalMetrics:
    first_pass_completion_rate: float
    after_one_retake_completion_rate: float
    invalid_false_acceptance_rate: float
    valid_false_rejection_rate: float
    repeatability_mean_absolute_difference_mm: float
    repeatability_p90_absolute_difference_mm: float
    repeatability_signed_difference_mm: float


def build_operational_report(
    sessions: Sequence[SessionOutcome],
    decisions: Sequence[QualityDecision],
    repeatability: Sequence[RepeatabilityObservation],
    cohort_reviews: Sequence[CohortReview],
    *,
    repeatability_review_ref: str,
    bootstrap_iterations: int = 2_000,
    seed: int = 20260712,
    minimum_participants: int = 200,
) -> dict[str, Any]:
    sessions, decisions, repeatability, cohort_reviews = _validate_inputs(
        sessions, decisions, repeatability, cohort_reviews, repeatability_review_ref
    )
    metrics = _metrics(sessions, decisions, repeatability)
    participant_ids = {item.participant_id for item in sessions}
    dataset_checks = {
        "minimum_participants": len(participant_ids) >= minimum_participants,
        "participant_coverage": participant_ids
        == {item.participant_id for item in decisions}
        == {item.participant_id for item in repeatability},
        "required_cohort_dimensions": REQUIRED_COHORT_DIMENSIONS.issubset(
            {item.dimension for item in cohort_reviews}
        ),
        "repeatability_review_present": bool(repeatability_review_ref.strip()),
    }
    gate_checks = {
        "first_pass_completion_rate": metrics.first_pass_completion_rate >= 0.85,
        "after_one_retake_completion_rate": (metrics.after_one_retake_completion_rate >= 0.95),
        "invalid_false_acceptance_rate": metrics.invalid_false_acceptance_rate <= 0.02,
        "valid_false_rejection_rate": metrics.valid_false_rejection_rate <= 0.10,
    }
    cohort_results = _cohort_results(decisions, cohort_reviews, metrics)
    return {
        "schema_version": "nailsize-operational-report@1",
        "participant_count": len(participant_ids),
        "metrics": asdict(metrics),
        "confidence_intervals_95": _clustered_intervals(
            sessions,
            decisions,
            repeatability,
            iterations=bootstrap_iterations,
            seed=seed,
        ),
        "dataset_checks": dataset_checks,
        "gate_checks": gate_checks,
        "adequately_sampled_cohorts": cohort_results,
        "repeatability_review_ref": repeatability_review_ref,
        "passed": (
            all(dataset_checks.values())
            and all(gate_checks.values())
            and all(item["passed"] for item in cohort_results)
        ),
    }


def _metrics(
    sessions: Sequence[SessionOutcome],
    decisions: Sequence[QualityDecision],
    repeatability: Sequence[RepeatabilityObservation],
) -> OperationalMetrics:
    invalid = [item for item in decisions if not item.ground_truth_valid]
    valid = [item for item in decisions if item.ground_truth_valid]
    if not invalid or not valid:
        raise ValueError("Quality decisions require valid and invalid ground-truth examples")
    absolute_differences, signed_differences = _repeatability_differences(repeatability)
    return OperationalMetrics(
        first_pass_completion_rate=float(np.mean([item.attempts_complete[0] for item in sessions])),
        after_one_retake_completion_rate=float(
            np.mean([any(item.attempts_complete) for item in sessions])
        ),
        invalid_false_acceptance_rate=float(np.mean([item.system_accepted for item in invalid])),
        valid_false_rejection_rate=float(np.mean([not item.system_accepted for item in valid])),
        repeatability_mean_absolute_difference_mm=float(np.mean(absolute_differences)),
        repeatability_p90_absolute_difference_mm=float(np.quantile(absolute_differences, 0.90)),
        repeatability_signed_difference_mm=float(np.mean(signed_differences)),
    )


def _repeatability_differences(
    observations: Sequence[RepeatabilityObservation],
) -> tuple[np.ndarray[Any, np.dtype[np.float64]], np.ndarray[Any, np.dtype[np.float64]]]:
    by_participant: dict[str, list[RepeatabilityObservation]] = defaultdict(list)
    for item in observations:
        by_participant[item.participant_id].append(item)
    signed: list[float] = []
    for participant_observations in by_participant.values():
        if len(participant_observations) != 2:
            raise ValueError("Each repeatability participant requires exactly two capture sets")
        first, second = sorted(participant_observations, key=lambda item: item.repetition_id)
        signed.extend(
            second.widths_mm[nail] - first.widths_mm[nail] for nail in sorted(EXPECTED_NAILS)
        )
    signed_array = np.asarray(signed, dtype=float)
    return np.abs(signed_array), signed_array


def _cohort_results(
    decisions: Sequence[QualityDecision],
    reviews: Sequence[CohortReview],
    overall: OperationalMetrics,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for review in sorted(reviews, key=lambda item: (item.dimension, item.value)):
        cohort = [item for item in decisions if item.cohorts.get(review.dimension) == review.value]
        invalid = [item for item in cohort if not item.ground_truth_valid]
        valid = [item for item in cohort if item.ground_truth_valid]
        if not invalid or not valid:
            raise ValueError(
                "Declared adequate cohorts require valid and invalid examples: "
                f"{review.dimension}={review.value}"
            )
        false_acceptance = float(np.mean([item.system_accepted for item in invalid]))
        false_rejection = float(np.mean([not item.system_accepted for item in valid]))
        results.append(
            {
                "dimension": review.dimension,
                "value": review.value,
                "participant_count": len({item.participant_id for item in cohort}),
                "decision_count": len(cohort),
                "invalid_false_acceptance_rate": false_acceptance,
                "valid_false_rejection_rate": false_rejection,
                "false_acceptance_gap_vs_overall": abs(
                    false_acceptance - overall.invalid_false_acceptance_rate
                ),
                "false_rejection_gap_vs_overall": abs(
                    false_rejection - overall.valid_false_rejection_rate
                ),
                "parity_review_ref": review.parity_review_ref,
                "passed": bool(review.parity_review_ref.strip()),
            }
        )
    return results


def _clustered_intervals(
    sessions: Sequence[SessionOutcome],
    decisions: Sequence[QualityDecision],
    repeatability: Sequence[RepeatabilityObservation],
    *,
    iterations: int,
    seed: int,
) -> dict[str, dict[str, float]]:
    if iterations < 100:
        raise ValueError("At least 100 bootstrap iterations are required")
    session_by_id = {item.participant_id: item for item in sessions}
    decisions_by_id: dict[str, list[QualityDecision]] = defaultdict(list)
    repeatability_by_id: dict[str, list[RepeatabilityObservation]] = defaultdict(list)
    for item in decisions:
        decisions_by_id[item.participant_id].append(item)
    for item in repeatability:
        repeatability_by_id[item.participant_id].append(item)
    participant_ids = sorted(session_by_id)
    random = np.random.default_rng(seed)
    samples = {name: [] for name in OPERATIONAL_METRICS}
    for _ in range(iterations):
        chosen = random.choice(participant_ids, size=len(participant_ids), replace=True)
        sampled_sessions: list[SessionOutcome] = []
        sampled_decisions: list[QualityDecision] = []
        sampled_repeatability: list[RepeatabilityObservation] = []
        for occurrence, participant_id in enumerate(chosen):
            source_id = str(participant_id)
            cluster_id = f"bootstrap-{occurrence}"
            session = session_by_id[source_id]
            sampled_sessions.append(SessionOutcome(cluster_id, session.attempts_complete))
            sampled_decisions.extend(
                QualityDecision(
                    cluster_id,
                    item.ground_truth_valid,
                    item.system_accepted,
                    item.cohorts,
                )
                for item in decisions_by_id[source_id]
            )
            sampled_repeatability.extend(
                RepeatabilityObservation(cluster_id, item.repetition_id, item.widths_mm)
                for item in repeatability_by_id[source_id]
            )
        try:
            iteration_metrics = _metrics(sampled_sessions, sampled_decisions, sampled_repeatability)
        except ValueError:
            continue
        for name in OPERATIONAL_METRICS:
            samples[name].append(getattr(iteration_metrics, name))
    minimum_valid = max(100, math.ceil(iterations * 0.90))
    if any(len(values) < minimum_valid for values in samples.values()):
        raise ValueError("Too few valid participant-clustered bootstrap samples")
    return {
        name: {
            "lower": float(np.quantile(values, 0.025)),
            "upper": float(np.quantile(values, 0.975)),
        }
        for name, values in samples.items()
    }


def _validate_inputs(
    sessions: Sequence[SessionOutcome],
    decisions: Sequence[QualityDecision],
    repeatability: Sequence[RepeatabilityObservation],
    cohort_reviews: Sequence[CohortReview],
    repeatability_review_ref: str,
) -> tuple[
    list[SessionOutcome],
    list[QualityDecision],
    list[RepeatabilityObservation],
    list[CohortReview],
]:
    session_records = list(sessions)
    decision_records = list(decisions)
    repeatability_records = list(repeatability)
    reviews = list(cohort_reviews)
    if not session_records or not decision_records or not repeatability_records:
        raise ValueError("Sessions, quality decisions, and repeatability records are required")
    if not repeatability_review_ref.strip():
        raise ValueError("A repeatability review reference is required")
    session_ids: set[str] = set()
    for item in session_records:
        _participant_id(item.participant_id)
        if item.participant_id in session_ids:
            raise ValueError("Each participant must have exactly one session outcome")
        session_ids.add(item.participant_id)
        if not 1 <= len(item.attempts_complete) <= 2 or any(
            not isinstance(value, bool) for value in item.attempts_complete
        ):
            raise ValueError("Session outcomes require one or two boolean attempts")
    for item in decision_records:
        _participant_id(item.participant_id)
        if not isinstance(item.ground_truth_valid, bool) or not isinstance(
            item.system_accepted, bool
        ):
            raise ValueError("Quality decisions must be boolean")
        if not isinstance(item.cohorts, dict) or any(
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(value, str)
            or not value.strip()
            for key, value in item.cohorts.items()
        ):
            raise ValueError("Quality cohorts must use non-empty keys and values")
    seen_repetitions: set[tuple[str, str]] = set()
    for item in repeatability_records:
        _participant_id(item.participant_id)
        if (
            not item.repetition_id.strip()
            or (item.participant_id, item.repetition_id) in seen_repetitions
        ):
            raise ValueError("Repeatability repetition IDs must be unique per participant")
        seen_repetitions.add((item.participant_id, item.repetition_id))
        if set(item.widths_mm) != EXPECTED_NAILS or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
            for value in item.widths_mm.values()
        ):
            raise ValueError("Repeatability records require ten positive finite nail widths")
    if not reviews or len({(item.dimension, item.value) for item in reviews}) != len(reviews):
        raise ValueError("Cohort reviews must be non-empty and unique")
    for item in reviews:
        if (
            not item.dimension.strip()
            or not item.value.strip()
            or not item.parity_review_ref.strip()
        ):
            raise ValueError("Cohort reviews require dimension, value, and parity review reference")
    _metrics(session_records, decision_records, repeatability_records)
    return session_records, decision_records, repeatability_records, reviews


def _participant_id(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Participant IDs must be non-empty")


def load_study_bundle(
    path: Path,
) -> tuple[
    list[SessionOutcome],
    list[QualityDecision],
    list[RepeatabilityObservation],
    list[CohortReview],
    str,
]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    try:
        if payload["schema_version"] != "nailsize-operational-study@1":
            raise ValueError("Unsupported operational study bundle schema")
        sessions = [
            SessionOutcome(item["participant_id"], tuple(item["attempts_complete"]))
            for item in payload["session_outcomes"]
        ]
        decisions = [QualityDecision(**item) for item in payload["quality_decisions"]]
        repeatability = [RepeatabilityObservation(**item) for item in payload["repeatability"]]
        reviews = [CohortReview(**item) for item in payload["cohort_reviews"]]
        review_ref = payload["repeatability_review_ref"]
    except (KeyError, TypeError) as error:
        raise ValueError("Invalid operational study bundle") from error
    return sessions, decisions, repeatability, reviews, review_ref


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the operational validation report")
    parser.add_argument("study_bundle", type=Path)
    parser.add_argument("--bootstrap-iterations", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    sessions, decisions, repeatability, reviews, review_ref = load_study_bundle(
        arguments.study_bundle
    )
    report = build_operational_report(
        sessions,
        decisions,
        repeatability,
        reviews,
        repeatability_review_ref=review_ref,
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
