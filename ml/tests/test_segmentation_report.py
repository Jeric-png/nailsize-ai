import hashlib
import json
import sys

import numpy as np
import pytest

from nailsize_ml.holdout_lock import holdout_set_commitment
from nailsize_ml.segmentation_report import (
    SegmentationObservation,
    build_segmentation_evaluation_report,
    load_observations,
    main,
)


def _observations() -> list[SegmentationObservation]:
    return [
        SegmentationObservation("participant-1", "image-1", "image-1.npy", "image-1.npy"),
        SegmentationObservation("participant-2", "image-2", "image-2.npy", "image-2.npy"),
    ]


def _write_masks(tmp_path) -> tuple:
    predictions = tmp_path / "predictions"
    ground_truth = tmp_path / "ground-truth"
    predictions.mkdir()
    ground_truth.mkdir()
    for index in (1, 2):
        predicted = np.zeros((224, 160), dtype=np.float32)
        expected = np.zeros((224, 160), dtype=np.uint8)
        predicted[40:180, 45:120] = 0.9
        expected[40:180, 44:119] = 1
        np.save(predictions / f"image-{index}.npy", predicted)
        np.save(ground_truth / f"image-{index}.npy", expected)
    return predictions, ground_truth


def _write_holdout(tmp_path, observations=None) -> tuple:
    records = observations or _observations()
    holdout = {
        "schema_version": "nailsize-public-holdout-lock@1",
        "dataset_version": "study-1",
        "manifest_sha256": "c" * 64,
        "split_strategy": "sha256_participant_salt_v1",
        "split_salt_id": "salt-1",
        "split_thresholds": {"train": 0.7, "validation": 0.15, "test": 0.15},
        "test_record_count": len(records),
        "test_participant_count": len({item.participant_id for item in records}),
        "test_set_commitment_sha256": holdout_set_commitment(
            (item.participant_id, item.image_id) for item in records
        ),
        "holdout_purpose": "public_release_model_evaluation",
        "model_selection_access_prohibited": True,
        "threshold_tuning_access_prohibited": True,
        "relabeling_requires_new_dataset_version": True,
        "holdout_lock_review_ref": "holdout-review-1",
        "passed": True,
    }
    path = tmp_path / "holdout-lock-report.json"
    path.write_text(json.dumps(holdout), encoding="utf-8")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _build(tmp_path, **overrides):
    observations = overrides.pop("observations", _observations())
    predictions, ground_truth = _write_masks(tmp_path)
    holdout, holdout_checksum = _write_holdout(tmp_path, observations)
    arguments = {
        "prediction_mask_root": predictions,
        "ground_truth_mask_root": ground_truth,
        "dataset_version": "study-1",
        "model_version": "release-1",
        "model_sha256": "a" * 64,
        "holdout_lock_path": holdout,
        "expected_holdout_lock_sha256": holdout_checksum,
        "prediction_threshold": 0.5,
        "threshold_selection_ref": "validation-threshold-review-1",
        "segmentation_review_ref": "segmentation-review-1",
        "bootstrap_iterations": 100,
        "seed": 7,
    }
    arguments.update(overrides)
    return build_segmentation_evaluation_report(observations, **arguments)


def test_builds_private_holdout_linked_segmentation_report(tmp_path) -> None:
    report = _build(tmp_path)

    assert report["passed"] is True
    assert report["participant_count"] == 2
    assert report["nail_count"] == 2
    assert 0 < report["metrics"]["iou"] < 1
    assert report["metrics"]["p95_boundary_error_px"] > 0
    assert set(report["confidence_intervals_95"]) == {
        "iou",
        "dice",
        "mean_boundary_error_px",
        "p95_boundary_error_px",
    }
    rendered = json.dumps(report)
    assert "participant-1" not in rendered
    assert "image-1" not in rendered
    assert "predictions" not in rendered


def test_rejects_holdout_identity_count_and_checksum_drift(tmp_path) -> None:
    predictions, ground_truth = _write_masks(tmp_path)
    observations = _observations()
    holdout, checksum = _write_holdout(tmp_path, observations)
    common = {
        "prediction_mask_root": predictions,
        "ground_truth_mask_root": ground_truth,
        "dataset_version": "study-1",
        "model_version": "release-1",
        "model_sha256": "a" * 64,
        "holdout_lock_path": holdout,
        "expected_holdout_lock_sha256": checksum,
        "prediction_threshold": 0.5,
        "threshold_selection_ref": "threshold-review",
        "segmentation_review_ref": "segmentation-review",
        "bootstrap_iterations": 100,
    }
    with pytest.raises(ValueError, match="exactly match"):
        build_segmentation_evaluation_report(observations[:1], **common)
    with pytest.raises(ValueError, match="checksum"):
        build_segmentation_evaluation_report(
            observations, **(common | {"expected_holdout_lock_sha256": "0" * 64})
        )
    changed = [
        SegmentationObservation("participant-3", "image-1", "image-1.npy", "image-1.npy"),
        observations[1],
    ]
    with pytest.raises(ValueError, match="exactly match"):
        build_segmentation_evaluation_report(changed, **common)


@pytest.mark.parametrize("value", [2.0, np.nan])
def test_rejects_invalid_prediction_probabilities(tmp_path, value) -> None:
    observations = [
        SegmentationObservation("participant-1", "image-1", "image-1.npy", "image-1.npy")
    ]
    predictions = tmp_path / "predictions"
    ground_truth = tmp_path / "ground-truth"
    predictions.mkdir()
    ground_truth.mkdir()
    prediction = np.zeros((224, 160), dtype=np.float32)
    prediction[40:180, 45:120] = value
    expected = np.zeros((224, 160), dtype=np.uint8)
    expected[40:180, 44:119] = 1
    np.save(predictions / "image-1.npy", prediction)
    np.save(ground_truth / "image-1.npy", expected)
    holdout, checksum = _write_holdout(tmp_path, observations)
    with pytest.raises(ValueError, match="finite numeric|within"):
        build_segmentation_evaluation_report(
            observations,
            prediction_mask_root=predictions,
            ground_truth_mask_root=ground_truth,
            dataset_version="study-1",
            model_version="release-1",
            model_sha256="a" * 64,
            holdout_lock_path=holdout,
            expected_holdout_lock_sha256=checksum,
            prediction_threshold=0.5,
            threshold_selection_ref="threshold-review",
            segmentation_review_ref="segmentation-review",
            bootstrap_iterations=100,
        )


def test_applies_the_selected_prediction_threshold(tmp_path) -> None:
    with pytest.raises(ValueError, match="visible nail"):
        _build(tmp_path, prediction_threshold=0.95)


def test_load_observations_is_exact_and_cli_writes_nested_report(tmp_path, monkeypatch) -> None:
    observations = _observations()
    source = tmp_path / "observations.jsonl"
    source.write_text(
        "".join(
            json.dumps(asdict) + "\n"
            for asdict in [
                {
                    "participant_id": item.participant_id,
                    "image_id": item.image_id,
                    "prediction_probability_uri": item.prediction_probability_uri,
                    "ground_truth_mask_uri": item.ground_truth_mask_uri,
                }
                for item in observations
            ]
        ),
        encoding="utf-8",
    )
    assert load_observations(source) == observations
    predictions, ground_truth = _write_masks(tmp_path)
    holdout, checksum = _write_holdout(tmp_path, observations)
    output = tmp_path / "nested" / "segmentation-report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nailsize-segmentation-report",
            str(source),
            "--prediction-mask-root",
            str(predictions),
            "--ground-truth-mask-root",
            str(ground_truth),
            "--dataset-version",
            "study-1",
            "--model-version",
            "release-1",
            "--model-sha256",
            "a" * 64,
            "--holdout-lock-report",
            str(holdout),
            "--expected-holdout-lock-sha256",
            checksum,
            "--prediction-threshold",
            "0.5",
            "--threshold-selection-ref",
            "threshold-review",
            "--segmentation-review-ref",
            "segmentation-review",
            "--bootstrap-iterations",
            "100",
            "--output",
            str(output),
        ],
    )

    with pytest.raises(SystemExit, match="0"):
        main()
    assert json.loads(output.read_text(encoding="utf-8"))["passed"] is True

    source.write_text(
        json.dumps(
            {
                "participant_id": "participant-1",
                "image_id": "image-1",
                "prediction_probability_uri": "image-1.npy",
                "ground_truth_mask_uri": "image-1.npy",
                "private": True,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="line 1"):
        load_observations(source)
