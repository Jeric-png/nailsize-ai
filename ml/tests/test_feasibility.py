import json
from dataclasses import asdict

import pytest

from nailsize_ml.feasibility import (
    CAPTURE_PROTOCOL,
    EXPECTED_NAIL_CAPTURE,
    STUDY_SCHEMA_VERSION,
    FeasibilityCohortReview,
    FeasibilityObservation,
    build_feasibility_report,
    load_study_bundle,
)


def records(participant_count: int = 100) -> list[FeasibilityObservation]:
    return [
        FeasibilityObservation(
            participant_id=f"participant-{participant}",
            nail=nail,
            capture_type=capture_type,
            projected_width_mm=13.1,
            physical_width_mm=13.0,
            recommended_size=5,
            best_fit_size=5,
            cohorts={
                "skin_tone": "monk-5",
                "curvature": "medium",
                "width": "medium",
                "device": "phone-a",
            },
        )
        for participant in range(participant_count)
        for nail, capture_type in EXPECTED_NAIL_CAPTURE.items()
    ]


def reviews() -> list[FeasibilityCohortReview]:
    return [
        FeasibilityCohortReview(dimension, value, f"review-{dimension}-1")
        for dimension, value in (
            ("skin_tone", "monk-5"),
            ("curvature", "medium"),
            ("width", "medium"),
            ("device", "phone-a"),
        )
    ]


def build(observations: list[FeasibilityObservation], **overrides):
    arguments = {
        "dataset_version": "feasibility-2026-07",
        "capture_protocol": CAPTURE_PROTOCOL,
        "observations": observations,
        "cohort_reviews": reviews(),
        "feasibility_review_ref": "feasibility-review-1",
        "nail_tech_review_ref": "nail-tech-review-1",
        "bootstrap_iterations": 100,
    }
    arguments.update(overrides)
    return build_feasibility_report(**arguments)


def test_passing_four_photo_report_applies_every_measurement_and_size_gate() -> None:
    report = build(records())

    assert report["passed"] is True
    assert report["decision"] == "four_photo_validated"
    assert report["public_launch_may_continue"] is True
    assert report["participant_count"] == 100
    assert report["nail_count"] == 1_000
    assert all(report["dataset_checks"].values())
    assert all(report["overall"]["checks"].values())
    assert len(report["adequately_sampled_cohorts"]) == 4


def test_failed_error_target_stops_launch_and_requires_oblique_capture() -> None:
    observations = records()
    for index in range(101):
        observations[index] = FeasibilityObservation(
            **{
                **asdict(observations[index]),
                "projected_width_mm": 16.0,
                "recommended_size": 8,
            }
        )

    report = build(observations)

    assert report["passed"] is False
    assert report["decision"] == "oblique_required"
    assert report["public_launch_may_continue"] is False
    assert report["overall"]["checks"]["exact_or_adjacent_rate"] is False
    assert report["overall"]["checks"]["more_than_one_size_miss_rate"] is False


def test_small_study_fails_minimums_without_hiding_aggregate_results() -> None:
    report = build(records(99))

    assert report["passed"] is False
    assert report["participant_count"] == 99
    assert report["nail_count"] == 990
    assert report["dataset_checks"]["minimum_participants"] is False
    assert report["dataset_checks"]["minimum_nails"] is False
    assert report["decision"] == "insufficient_evidence"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda items: items[:-1], "exactly one observation"),
        (
            lambda items: [
                FeasibilityObservation(
                    **{
                        **asdict(items[0]),
                        "capture_type": "right_thumb",
                    }
                ),
                *items[1:],
            ],
            "approved four-photo capture type",
        ),
        (
            lambda items: [
                FeasibilityObservation(
                    **{
                        **asdict(items[0]),
                        "cohorts": {"device": "phone-a"},
                    }
                ),
                *items[1:],
            ],
            "exact approved cohort",
        ),
    ],
)
def test_rejects_incomplete_or_nonproduction_capture_records(mutation, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build(mutation(records(2)), minimum_participants=2, minimum_nails=20)


def test_requires_exact_protocol_and_observed_cohorts() -> None:
    with pytest.raises(ValueError, match="approved production four-photo"):
        build(records(2), capture_protocol="oblique-unapproved@1")
    altered_reviews = reviews()
    altered_reviews[0] = FeasibilityCohortReview("skin_tone", "missing", "review")
    with pytest.raises(ValueError, match="observed data"):
        build(records(2), cohort_reviews=altered_reviews)

    altered_records = records(2)
    altered_records[0] = FeasibilityObservation(
        **{**asdict(altered_records[0]), "participant_id": " participant-0"}
    )
    with pytest.raises(ValueError, match="edge whitespace"):
        build(altered_records, minimum_participants=2, minimum_nails=20)


def test_incomplete_review_evidence_returns_insufficient_report() -> None:
    missing_study_review = build(records(), nail_tech_review_ref="")
    missing_cohort_reviews = build(records(), cohort_reviews=[])

    assert missing_study_review["passed"] is False
    assert missing_study_review["decision"] == "insufficient_evidence"
    assert missing_study_review["dataset_checks"]["nail_tech_review_present"] is False
    assert missing_cohort_reviews["passed"] is False
    assert missing_cohort_reviews["decision"] == "insufficient_evidence"
    assert missing_cohort_reviews["dataset_checks"]["required_cohort_dimensions"] is False
    assert missing_cohort_reviews["dataset_checks"]["cohort_review_evidence_complete"] is False


def test_loads_exact_private_bundle_and_report_omits_participant_identifiers(tmp_path) -> None:
    observations = records(2)
    payload = {
        "schema_version": STUDY_SCHEMA_VERSION,
        "dataset_version": "feasibility-2026-07",
        "capture_protocol": CAPTURE_PROTOCOL,
        "observations": [asdict(item) for item in observations],
        "cohort_reviews": [asdict(item) for item in reviews()],
        "feasibility_review_ref": "feasibility-review-1",
        "nail_tech_review_ref": "nail-tech-review-1",
    }
    path = tmp_path / "study.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_study_bundle(path)
    report = build(loaded[2], minimum_participants=2, minimum_nails=20)
    rendered = json.dumps(report, sort_keys=True)

    assert loaded == (
        payload["dataset_version"],
        CAPTURE_PROTOCOL,
        observations,
        reviews(),
        payload["feasibility_review_ref"],
        payload["nail_tech_review_ref"],
    )
    assert "participant-0" not in rendered
    assert "participant_id" not in rendered
    assert "image" not in rendered
    assert "path" not in rendered


def test_loader_rejects_schema_drift_and_extra_record_fields(tmp_path) -> None:
    payload = {
        "schema_version": STUDY_SCHEMA_VERSION,
        "dataset_version": "feasibility-2026-07",
        "capture_protocol": CAPTURE_PROTOCOL,
        "observations": [{**asdict(records(1)[0]), "image_path": "private.png"}],
        "cohort_reviews": [asdict(item) for item in reviews()],
        "feasibility_review_ref": "feasibility-review-1",
        "nail_tech_review_ref": "nail-tech-review-1",
    }
    path = tmp_path / "study.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid feasibility study bundle"):
        load_study_bundle(path)

    payload["observations"] = []
    payload["unexpected"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="exact schema"):
        load_study_bundle(path)
