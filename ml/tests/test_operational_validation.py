import json

import pytest

from nailsize_ml.operational_validation import (
    EXPECTED_NAILS,
    CohortReview,
    QualityDecision,
    RepeatabilityObservation,
    SessionOutcome,
    build_operational_report,
    load_study_bundle,
)


def records(participant_count: int = 200):
    sessions = [SessionOutcome(f"p-{index}", (True,)) for index in range(participant_count)]
    decisions = []
    repeatability = []
    for index in range(participant_count):
        participant_id = f"p-{index}"
        cohorts = {
            "skin_tone": "monk-5",
            "curvature": "medium",
            "width": "medium",
            "device": "phone-a",
        }
        decisions.extend(
            (
                QualityDecision(participant_id, True, True, cohorts),
                QualityDecision(participant_id, False, False, cohorts),
            )
        )
        first = {
            nail: 12.0 + nail_index * 0.1 for nail_index, nail in enumerate(sorted(EXPECTED_NAILS))
        }
        second = {nail: width + 0.1 for nail, width in first.items()}
        repeatability.extend(
            (
                RepeatabilityObservation(participant_id, "a", first),
                RepeatabilityObservation(participant_id, "b", second),
            )
        )
    reviews = [
        CohortReview(dimension, value, f"review-{dimension}")
        for dimension, value in (
            ("skin_tone", "monk-5"),
            ("curvature", "medium"),
            ("width", "medium"),
            ("device", "phone-a"),
        )
    ]
    return sessions, decisions, repeatability, reviews


def test_passing_report_enforces_completion_rejection_and_repeatability_contracts() -> None:
    sessions, decisions, repeatability, reviews = records()

    report = build_operational_report(
        sessions,
        decisions,
        repeatability,
        reviews,
        repeatability_review_ref="repeatability-review-1",
        bootstrap_iterations=100,
    )

    assert report["passed"] is True
    assert report["participant_count"] == 200
    assert report["metrics"]["first_pass_completion_rate"] == 1.0
    assert report["metrics"]["invalid_false_acceptance_rate"] == 0.0
    assert report["metrics"]["repeatability_mean_absolute_difference_mm"] == pytest.approx(0.1)
    assert len(report["adequately_sampled_cohorts"]) == 4
    assert all(report["gate_checks"].values())


def test_report_fails_numeric_gates_and_dataset_minimum_without_hiding_metrics() -> None:
    sessions, decisions, repeatability, reviews = records(10)
    sessions[0] = SessionOutcome("p-0", (False, False))
    decisions[0] = QualityDecision("p-0", True, False, decisions[0].cohorts)
    decisions[1] = QualityDecision("p-0", False, True, decisions[1].cohorts)

    report = build_operational_report(
        sessions,
        decisions,
        repeatability,
        reviews,
        repeatability_review_ref="repeatability-review-1",
        bootstrap_iterations=100,
    )

    assert report["passed"] is False
    assert report["dataset_checks"]["minimum_participants"] is False
    assert report["gate_checks"] == {
        "first_pass_completion_rate": True,
        "after_one_retake_completion_rate": False,
        "invalid_false_acceptance_rate": False,
        "valid_false_rejection_rate": True,
    }


def test_participant_coverage_and_required_fairness_dimensions_fail_closed() -> None:
    sessions, decisions, repeatability, reviews = records(5)
    decisions = [item for item in decisions if item.participant_id != "p-4"]
    reviews = reviews[:-1]

    report = build_operational_report(
        sessions,
        decisions,
        repeatability,
        reviews,
        repeatability_review_ref="repeatability-review-1",
        bootstrap_iterations=100,
        minimum_participants=5,
    )

    assert report["passed"] is False
    assert report["dataset_checks"]["participant_coverage"] is False
    assert report["dataset_checks"]["required_cohort_dimensions"] is False


def test_rejects_incomplete_repeatability_and_unreviewed_cohorts() -> None:
    sessions, decisions, repeatability, reviews = records(2)
    with pytest.raises(ValueError, match="exactly two"):
        build_operational_report(
            sessions,
            decisions,
            repeatability[:-1],
            reviews,
            repeatability_review_ref="review",
            bootstrap_iterations=100,
        )

    reviews[0] = CohortReview("skin_tone", "monk-5", "")
    with pytest.raises(ValueError, match="parity review"):
        build_operational_report(
            sessions,
            decisions,
            repeatability,
            reviews,
            repeatability_review_ref="review",
            bootstrap_iterations=100,
        )


def test_loads_versioned_private_study_bundle_without_images(tmp_path) -> None:
    sessions, decisions, repeatability, reviews = records(1)
    payload = {
        "schema_version": "nailsize-operational-study@1",
        "session_outcomes": [
            {
                "participant_id": item.participant_id,
                "attempts_complete": list(item.attempts_complete),
            }
            for item in sessions
        ],
        "quality_decisions": [item.__dict__ for item in decisions],
        "repeatability": [item.__dict__ for item in repeatability],
        "cohort_reviews": [item.__dict__ for item in reviews],
        "repeatability_review_ref": "repeatability-review-1",
    }
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_study_bundle(path)

    assert loaded == (sessions, decisions, repeatability, reviews, "repeatability-review-1")


def test_rejects_unknown_bundle_schema_and_malformed_cohort_types(tmp_path) -> None:
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps({"schema_version": "unknown"}), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported"):
        load_study_bundle(path)

    sessions, decisions, repeatability, reviews = records(1)
    decisions[0] = QualityDecision("p-0", True, True, {"device": 1})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="cohorts"):
        build_operational_report(
            sessions,
            decisions,
            repeatability,
            reviews,
            repeatability_review_ref="review",
            bootstrap_iterations=100,
        )
