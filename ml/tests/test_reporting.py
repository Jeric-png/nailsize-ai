import json

import pytest

from nailsize_ml.reporting import (
    AccuracyObservation,
    build_accuracy_report,
    load_observations,
    participant_clustered_confidence_intervals,
)


def observation(
    participant: str,
    *,
    error: float = 0.1,
    predicted_size: int = 5,
    ground_truth_size: int = 5,
    tone: str = "monk-5",
) -> AccuracyObservation:
    return AccuracyObservation(
        participant_id=participant,
        predicted_width_mm=13.0 + error,
        ground_truth_width_mm=13.0,
        predicted_size=predicted_size,
        ground_truth_size=ground_truth_size,
        cohorts={"skin_tone": tone, "device": "phone-a"},
    )


def test_report_applies_dataset_overall_and_declared_cohort_gates() -> None:
    records = [observation(f"p-{index}") for index in range(200) for _ in range(10)]

    report = build_accuracy_report(
        records,
        [("skin_tone", "monk-5"), ("device", "phone-a")],
        bootstrap_iterations=100,
    )

    assert report["passed"] is True
    assert report["participant_count"] == 200
    assert report["nail_count"] == 2_000
    assert report["overall"]["metrics"]["width_mae_mm"] == pytest.approx(0.1)
    assert all(item["passed"] for item in report["adequately_sampled_cohorts"])


def test_report_fails_closed_for_small_dataset_and_underperforming_cohort() -> None:
    records = [observation("p-good") for _ in range(9)]
    records.append(
        observation("p-bad", error=1.0, predicted_size=8, ground_truth_size=5, tone="monk-10")
    )

    report = build_accuracy_report(
        records,
        [("skin_tone", "monk-10")],
        bootstrap_iterations=100,
    )

    assert report["passed"] is False
    assert report["dataset_checks"] == {
        "minimum_participants": False,
        "minimum_nails": False,
    }
    cohort = report["adequately_sampled_cohorts"][0]
    assert cohort["checks"] == {"width_mae_mm": False, "exact_size_rate_gap": False}


def test_clustered_bootstrap_is_deterministic_and_validates_iterations() -> None:
    records = [observation("p-1", error=0.1), observation("p-2", error=0.3)]

    first = participant_clustered_confidence_intervals(records, iterations=100, seed=7)
    second = participant_clustered_confidence_intervals(records, iterations=100, seed=7)

    assert first == second
    assert first["width_mae_mm"] == pytest.approx({"lower": 0.1, "upper": 0.3})
    with pytest.raises(ValueError, match="At least 100"):
        participant_clustered_confidence_intervals(records, iterations=99, seed=7)


def test_declared_cohort_requires_data_and_unique_declaration() -> None:
    records = [observation("p-1")]
    with pytest.raises(ValueError, match="no observations"):
        build_accuracy_report(records, [("device", "missing")], bootstrap_iterations=100)
    with pytest.raises(ValueError, match="unique"):
        build_accuracy_report(
            records,
            [("device", "phone-a"), ("device", "phone-a")],
            bootstrap_iterations=100,
        )


def test_jsonl_loader_rejects_malformed_records(tmp_path) -> None:
    path = tmp_path / "observations.jsonl"
    path.write_text(json.dumps(observation("p-1").__dict__) + "\n", encoding="utf-8")
    assert load_observations(path) == [observation("p-1")]

    path.write_text('{"participant_id":', encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        load_observations(path)
