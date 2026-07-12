import json
import sys
from dataclasses import asdict

import pytest

from nailsize_ml.size_calibration import (
    CHART_WIDTHS_MM,
    CurvatureReview,
    SizeCalibrationObservation,
    build_size_calibration_report,
    load_observations,
    main,
)


def observations(participant_count: int = 200) -> list[SizeCalibrationObservation]:
    return [
        SizeCalibrationObservation(
            participant_id=f"participant-{participant_index:03d}",
            nail_id=f"nail-{nail_index}",
            physical_width_mm=CHART_WIDTHS_MM[nail_index],
            physical_best_fit_size=nail_index,
            curvature_cohort="medium",
        )
        for participant_index in range(participant_count)
        for nail_index in range(10)
    ]


def test_passing_report_links_physical_best_fit_to_exact_chart() -> None:
    report = build_size_calibration_report(
        observations(),
        [CurvatureReview("medium", "curvature-review-1")],
        dataset_version="holdout-1",
        calibration_review_ref="calibration-review-1",
        bootstrap_iterations=100,
    )

    assert report["schema_version"] == "nailsize-size-calibration-report@1"
    assert report["chart_id"] == "platform-default"
    assert report["chart_version"] == "1"
    assert report["participant_count"] == 200
    assert report["nail_count"] == 2000
    assert report["metrics"]["exact_size_rate"] == 1.0
    assert report["metrics"]["mean_best_fit_tip_margin_mm"] == 0.0
    assert all(report["dataset_checks"].values())
    assert all(report["gate_checks"].values())
    assert report["passed"] is True


def test_report_fails_numeric_gates_and_unmappable_widths_without_hiding_bias() -> None:
    records = observations(2)
    records[0] = SizeCalibrationObservation(
        records[0].participant_id,
        records[0].nail_id,
        18.5,
        0,
        "medium",
    )
    records[1] = SizeCalibrationObservation(
        records[1].participant_id,
        records[1].nail_id,
        CHART_WIDTHS_MM[0],
        3,
        "medium",
    )
    records[2] = SizeCalibrationObservation(
        records[2].participant_id,
        records[2].nail_id,
        CHART_WIDTHS_MM[0],
        3,
        "medium",
    )

    report = build_size_calibration_report(
        records,
        [CurvatureReview("medium", "curvature-review-1")],
        dataset_version="holdout-1",
        calibration_review_ref="calibration-review-1",
        bootstrap_iterations=100,
        minimum_participants=2,
        minimum_nails=20,
    )

    assert report["passed"] is False
    assert report["dataset_checks"]["all_widths_mappable"] is False
    assert report["gate_checks"]["exact_size_rate"] is False
    assert report["gate_checks"]["more_than_one_size_miss_rate"] is False
    assert report["metrics"]["unmappable_rate"] == pytest.approx(0.05)
    assert report["metrics"]["mean_best_fit_tip_margin_mm"] < 0


def test_curvature_cohort_reports_bias_and_requires_exact_rate_parity() -> None:
    records = observations(10)
    for index in range(20):
        item = records[index]
        records[index] = SizeCalibrationObservation(
            item.participant_id,
            item.nail_id,
            CHART_WIDTHS_MM[0],
            3,
            "high",
        )
    reviews = [
        CurvatureReview("high", "high-review"),
        CurvatureReview("medium", "medium-review"),
    ]

    report = build_size_calibration_report(
        records,
        reviews,
        dataset_version="holdout-1",
        calibration_review_ref="calibration-review-1",
        bootstrap_iterations=100,
        minimum_participants=10,
        minimum_nails=100,
    )

    high = next(
        item for item in report["adequately_sampled_curvature_cohorts"] if item["cohort"] == "high"
    )
    assert high["metrics"]["exact_size_rate"] == 0.0
    assert high["metrics"]["mean_best_fit_tip_margin_mm"] == -3.0
    assert high["checks"]["exact_size_rate_gap"] is False
    assert report["passed"] is False


def test_rejects_duplicate_or_malformed_observations_and_unreviewed_cohorts() -> None:
    records = observations(1)
    with pytest.raises(ValueError, match="unique and well formed"):
        build_size_calibration_report(
            records + [records[0]],
            [CurvatureReview("medium", "review")],
            dataset_version="holdout-1",
            calibration_review_ref="review",
            bootstrap_iterations=100,
        )

    with pytest.raises(ValueError, match="Curvature reviews"):
        build_size_calibration_report(
            records,
            [CurvatureReview("absent", "review")],
            dataset_version="holdout-1",
            calibration_review_ref="review",
            bootstrap_iterations=100,
        )

    malformed = SizeCalibrationObservation(1, "nail-1", 14.0, 4, "medium")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="well formed"):
        build_size_calibration_report(
            [malformed],
            [CurvatureReview("medium", "review")],
            dataset_version="holdout-1",
            calibration_review_ref="review",
            bootstrap_iterations=100,
        )


def test_loads_exact_privacy_safe_jsonl_contract(tmp_path) -> None:
    path = tmp_path / "calibration.jsonl"
    payload = {
        "participant_id": "participant-001",
        "nail_id": "left-index",
        "physical_width_mm": 14.0,
        "physical_best_fit_size": 4,
        "curvature_cohort": "medium",
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    assert load_observations(path) == [SizeCalibrationObservation(**payload)]

    payload["unexpected"] = "private"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        load_observations(path)


def test_rejects_unreadable_observations_invalid_reviews_and_short_bootstrap(tmp_path) -> None:
    with pytest.raises(ValueError, match="could not be read"):
        load_observations(tmp_path / "missing.jsonl")

    records = observations(1)
    with pytest.raises(ValueError, match="Dataset version"):
        build_size_calibration_report(
            records,
            [CurvatureReview("medium", "review")],
            dataset_version="",
            calibration_review_ref="review",
            bootstrap_iterations=100,
        )
    with pytest.raises(ValueError, match="100 bootstrap"):
        build_size_calibration_report(
            records,
            [CurvatureReview("medium", "review")],
            dataset_version="holdout-1",
            calibration_review_ref="review",
            bootstrap_iterations=99,
            minimum_participants=1,
            minimum_nails=10,
        )
    with pytest.raises(ValueError, match="positive integers"):
        build_size_calibration_report(
            records,
            [CurvatureReview("medium", "review")],
            dataset_version="holdout-1",
            calibration_review_ref="review",
            bootstrap_iterations=100,
            minimum_participants=0,
        )


def test_cli_writes_a_passing_nested_report(tmp_path, monkeypatch) -> None:
    source = tmp_path / "calibration.jsonl"
    source.write_text(
        "".join(json.dumps(asdict(item)) + "\n" for item in observations()),
        encoding="utf-8",
    )
    output = tmp_path / "nested" / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nailsize-size-calibration-report",
            str(source),
            "--dataset-version",
            "holdout-1",
            "--calibration-review-ref",
            "calibration-review-1",
            "--curvature-review",
            " medium = curvature-review-1 ",
            "--bootstrap-iterations",
            "100",
            "--output",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as raised:
        main()

    assert raised.value.code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["passed"] is True
