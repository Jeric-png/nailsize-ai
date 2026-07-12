import argparse
import json
import math
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .reporting import (
    REQUIRED_COHORT_DIMENSIONS,
    AccuracyObservation,
    build_accuracy_report,
)

SCHEMA_VERSION = "nailsize-feasibility-report@1"
STUDY_SCHEMA_VERSION = "nailsize-feasibility-study@1"
CAPTURE_PROTOCOL = "production-four-photo@1"
EXPECTED_NAIL_CAPTURE = {
    **{
        f"{side}_{digit}": f"{side}_fingers"
        for side in ("left", "right")
        for digit in ("index", "middle", "ring", "pinky")
    },
    "left_thumb": "left_thumb",
    "right_thumb": "right_thumb",
}
EXPECTED_NAILS = frozenset(EXPECTED_NAIL_CAPTURE)
EXPECTED_CAPTURE_TYPES = frozenset(EXPECTED_NAIL_CAPTURE.values())
_DATASET_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True)
class FeasibilityObservation:
    participant_id: str
    nail: str
    capture_type: str
    projected_width_mm: float
    physical_width_mm: float
    recommended_size: int
    best_fit_size: int
    cohorts: dict[str, str]


@dataclass(frozen=True)
class FeasibilityCohortReview:
    dimension: str
    value: str
    adequate_sample_review_ref: str


def build_feasibility_report(
    *,
    dataset_version: str,
    capture_protocol: str,
    observations: Sequence[FeasibilityObservation],
    cohort_reviews: Sequence[FeasibilityCohortReview],
    feasibility_review_ref: str,
    nail_tech_review_ref: str,
    bootstrap_iterations: int = 2_000,
    seed: int = 20260712,
    minimum_participants: int = 100,
    minimum_nails: int = 1_000,
) -> dict[str, Any]:
    records, reviews = _validate_inputs(
        dataset_version=dataset_version,
        capture_protocol=capture_protocol,
        observations=observations,
        cohort_reviews=cohort_reviews,
        feasibility_review_ref=feasibility_review_ref,
        nail_tech_review_ref=nail_tech_review_ref,
    )
    accuracy_records = [
        AccuracyObservation(
            participant_id=item.participant_id,
            predicted_width_mm=item.projected_width_mm,
            ground_truth_width_mm=item.physical_width_mm,
            predicted_size=item.recommended_size,
            ground_truth_size=item.best_fit_size,
            cohorts=item.cohorts,
        )
        for item in records
    ]
    accuracy = build_accuracy_report(
        accuracy_records,
        [(item.dimension, item.value) for item in reviews],
        bootstrap_iterations=bootstrap_iterations,
        seed=seed,
        minimum_participants=minimum_participants,
        minimum_nails=minimum_nails,
    )
    review_refs = {
        (item.dimension, item.value): item.adequate_sample_review_ref for item in reviews
    }
    cohort_results = [
        {
            **item,
            "adequate_sample_review_ref": review_refs[(item["dimension"], item["value"])],
        }
        for item in accuracy["adequately_sampled_cohorts"]
    ]
    dataset_checks = {
        **accuracy["dataset_checks"],
        "production_four_photo_protocol": True,
        "complete_ten_nails_per_participant": True,
        "exact_capture_mapping": True,
        "feasibility_review_present": _review_ref(feasibility_review_ref),
        "nail_tech_review_present": _review_ref(nail_tech_review_ref),
        "cohort_review_evidence_complete": bool(reviews)
        and all(_review_ref(item.adequate_sample_review_ref) for item in reviews),
    }
    passed = (
        all(dataset_checks.values())
        and accuracy["overall"]["passed"]
        and all(item["passed"] for item in cohort_results)
    )
    if passed:
        decision = "four_photo_validated"
    elif not all(dataset_checks.values()):
        decision = "insufficient_evidence"
    else:
        decision = "oblique_required"
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": dataset_version,
        "capture_protocol": capture_protocol,
        "participant_count": accuracy["participant_count"],
        "nail_count": accuracy["nail_count"],
        "capture_types": sorted(EXPECTED_CAPTURE_TYPES),
        "dataset_checks": dataset_checks,
        "overall": accuracy["overall"],
        "adequately_sampled_cohorts": cohort_results,
        "feasibility_review_ref": feasibility_review_ref,
        "nail_tech_review_ref": nail_tech_review_ref,
        "decision": decision,
        "public_launch_may_continue": passed,
        "passed": passed,
    }


def _validate_inputs(
    *,
    dataset_version: str,
    capture_protocol: str,
    observations: Sequence[FeasibilityObservation],
    cohort_reviews: Sequence[FeasibilityCohortReview],
    feasibility_review_ref: str,
    nail_tech_review_ref: str,
) -> tuple[list[FeasibilityObservation], list[FeasibilityCohortReview]]:
    if not isinstance(dataset_version, str) or _DATASET_VERSION.fullmatch(dataset_version) is None:
        raise ValueError("Dataset version must be a bounded immutable identifier")
    if capture_protocol != CAPTURE_PROTOCOL:
        raise ValueError("Feasibility requires the approved production four-photo protocol")
    if not _optional_review_ref(feasibility_review_ref) or not _optional_review_ref(
        nail_tech_review_ref
    ):
        raise ValueError("Study review references must be strings without edge whitespace")
    records = list(observations)
    if not records:
        raise ValueError("Feasibility observations are required")
    by_participant: dict[str, list[FeasibilityObservation]] = defaultdict(list)
    for item in records:
        if (
            not isinstance(item.participant_id, str)
            or not item.participant_id
            or item.participant_id != item.participant_id.strip()
        ):
            raise ValueError("Participant IDs must be non-empty and contain no edge whitespace")
        if item.nail not in EXPECTED_NAILS:
            raise ValueError("Feasibility observations require a recognized nail")
        if item.capture_type != EXPECTED_NAIL_CAPTURE[item.nail]:
            raise ValueError("Every nail must map to its approved four-photo capture type")
        for value in (item.projected_width_mm, item.physical_width_mm):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError("Projected and physical widths must be positive finite numbers")
        for value in (item.recommended_size, item.best_fit_size):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 9:
                raise ValueError("Recommended and best-fit sizes must use chart sizes 0 through 9")
        if (
            not isinstance(item.cohorts, dict)
            or set(item.cohorts) != REQUIRED_COHORT_DIMENSIONS
            or any(
                not isinstance(value, str) or not value or value != value.strip()
                for value in item.cohorts.values()
            )
        ):
            raise ValueError("Every observation requires the exact approved cohort dimensions")
        by_participant[item.participant_id].append(item)
    for participant_records in by_participant.values():
        nails = [item.nail for item in participant_records]
        if len(nails) != len(EXPECTED_NAILS) or set(nails) != EXPECTED_NAILS:
            raise ValueError("Every participant requires exactly one observation for all ten nails")
        if {item.capture_type for item in participant_records} != EXPECTED_CAPTURE_TYPES:
            raise ValueError("Every participant must complete all four approved capture types")

    reviews = list(cohort_reviews)
    review_keys = [(item.dimension, item.value) for item in reviews]
    if len(set(review_keys)) != len(review_keys):
        raise ValueError("Adequately sampled cohort reviews must be unique")
    observed_cohorts = {
        (dimension, value) for item in records for dimension, value in item.cohorts.items()
    }
    for item in reviews:
        if (
            item.dimension not in REQUIRED_COHORT_DIMENSIONS
            or not isinstance(item.value, str)
            or not item.value
            or item.value != item.value.strip()
            or not _optional_review_ref(item.adequate_sample_review_ref)
            or (item.dimension, item.value) not in observed_cohorts
        ):
            raise ValueError(
                "Every declared cohort requires an approved dimension and observed data"
            )
    return records, reviews


def _review_ref(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _optional_review_ref(value: Any) -> bool:
    return isinstance(value, str) and value == value.strip()


def load_study_bundle(
    path: Path,
) -> tuple[
    str,
    str,
    list[FeasibilityObservation],
    list[FeasibilityCohortReview],
    str,
    str,
]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Could not read the feasibility study bundle") from error
    expected_fields = {
        "schema_version",
        "dataset_version",
        "capture_protocol",
        "observations",
        "cohort_reviews",
        "feasibility_review_ref",
        "nail_tech_review_ref",
    }
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise ValueError("Feasibility study bundle fields do not match the exact schema")
    if payload.get("schema_version") != STUDY_SCHEMA_VERSION:
        raise ValueError("Unsupported feasibility study bundle schema")
    try:
        observations = [FeasibilityObservation(**item) for item in payload["observations"]]
        reviews = [FeasibilityCohortReview(**item) for item in payload["cohort_reviews"]]
    except (TypeError, KeyError) as error:
        raise ValueError("Invalid feasibility study bundle records") from error
    return (
        payload["dataset_version"],
        payload["capture_protocol"],
        observations,
        reviews,
        payload["feasibility_review_ref"],
        payload["nail_tech_review_ref"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a fail-closed four-photo feasibility report"
    )
    parser.add_argument("study_bundle", type=Path)
    parser.add_argument("--bootstrap-iterations", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    dataset_version, protocol, observations, reviews, feasibility_ref, nail_tech_ref = (
        load_study_bundle(arguments.study_bundle)
    )
    report = build_feasibility_report(
        dataset_version=dataset_version,
        capture_protocol=protocol,
        observations=observations,
        cohort_reviews=reviews,
        feasibility_review_ref=feasibility_ref,
        nail_tech_review_ref=nail_tech_ref,
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
