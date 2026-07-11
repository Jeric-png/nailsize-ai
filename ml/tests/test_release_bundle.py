import hashlib
import json
from copy import deepcopy

import pytest

from nailsize_ml.model_card import render_model_card
from nailsize_ml.release_bundle import verify_release_bundle


def _metadata(checksum: str) -> dict:
    return {
        "model_name": "NailSize segmentation",
        "model_version": "release-1",
        "model_sha256": checksum,
        "dataset_version": "holdout-1",
        "intended_use": "Projected nail-width estimation for bare natural nails.",
        "out_of_scope": ["Artificial nails", "Diagnosing nail conditions"],
        "limitations": ["Measures projected width, not curved surface width."],
        "segmentation_metrics": {
            "iou": 0.9,
            "dice": 0.95,
            "mean_boundary_error_px": 0.4,
            "p95_boundary_error_px": 0.8,
        },
        "onnx_parity_max_abs_error": 0.00001,
        "approvals": {
            "model_owner": "Research review R-1",
            "nail_tech": "Nail-tech review N-1",
            "privacy_security": "Privacy review P-1",
        },
    }


def _accuracy_report() -> dict:
    metrics = {
        "width_mae_mm": 0.4,
        "width_p90_error_mm": 0.8,
        "signed_bias_mm": 0.05,
        "exact_size_rate": 0.92,
        "exact_or_adjacent_rate": 0.995,
        "more_than_one_size_miss_rate": 0.005,
    }
    return {
        "schema_version": "nailsize-accuracy-report@1",
        "participant_count": 200,
        "nail_count": 2000,
        "passed": True,
        "dataset_checks": {
            "minimum_participants": True,
            "minimum_nails": True,
            "required_cohort_dimensions": True,
        },
        "overall": {
            "metrics": metrics,
            "confidence_intervals_95": {
                name: {"lower": value * 0.9, "upper": value * 1.1}
                for name, value in metrics.items()
            },
            "checks": {name: True for name in metrics},
            "passed": True,
        },
        "adequately_sampled_cohorts": [
            {
                "dimension": dimension,
                "value": value,
                "participant_count": 50,
                "nail_count": 500,
                "metrics": {"width_mae_mm": 0.45, "exact_size_rate": 0.91},
                "checks": {"width_mae_mm": True, "exact_size_rate_gap": True},
                "passed": True,
            }
            for dimension, value in _cohorts()
        ],
    }


def _operational_report() -> dict:
    return {
        "schema_version": "nailsize-operational-report@1",
        "participant_count": 200,
        "metrics": {
            "first_pass_completion_rate": 0.9,
            "after_one_retake_completion_rate": 0.97,
            "invalid_false_acceptance_rate": 0.01,
            "valid_false_rejection_rate": 0.05,
            "repeatability_mean_absolute_difference_mm": 0.1,
            "repeatability_p90_absolute_difference_mm": 0.2,
            "repeatability_signed_difference_mm": 0.01,
        },
        "confidence_intervals_95": {
            name: {"lower": value * 0.9, "upper": value * 1.1}
            for name, value in {
                "first_pass_completion_rate": 0.9,
                "after_one_retake_completion_rate": 0.97,
                "invalid_false_acceptance_rate": 0.01,
                "valid_false_rejection_rate": 0.05,
                "repeatability_mean_absolute_difference_mm": 0.1,
                "repeatability_p90_absolute_difference_mm": 0.2,
                "repeatability_signed_difference_mm": 0.01,
            }.items()
        },
        "dataset_checks": {
            "minimum_participants": True,
            "participant_coverage": True,
            "required_cohort_dimensions": True,
            "repeatability_review_present": True,
        },
        "gate_checks": {
            "first_pass_completion_rate": True,
            "after_one_retake_completion_rate": True,
            "invalid_false_acceptance_rate": True,
            "valid_false_rejection_rate": True,
        },
        "adequately_sampled_cohorts": [
            {
                "dimension": dimension,
                "value": value,
                "participant_count": 50,
                "decision_count": 100,
                "parity_review_ref": f"review-{dimension}",
                "passed": True,
            }
            for dimension, value in _cohorts()
        ],
        "repeatability_review_ref": "repeatability-review-1",
        "passed": True,
    }


def _cohorts() -> tuple[tuple[str, str], ...]:
    return (
        ("skin_tone", "monk-5"),
        ("curvature", "medium"),
        ("width", "medium"),
        ("device", "phone-a"),
    )


def _write_bundle(directory):
    model = directory / "nail-segmentation.onnx"
    model.write_bytes(b"release-model-bytes")
    checksum = hashlib.sha256(model.read_bytes()).hexdigest()
    metadata = _metadata(checksum)
    accuracy = _accuracy_report()
    operational = _operational_report()
    (directory / "model-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (directory / "accuracy-report.json").write_text(json.dumps(accuracy), encoding="utf-8")
    (directory / "operational-report.json").write_text(json.dumps(operational), encoding="utf-8")
    (directory / "model-card.md").write_text(
        render_model_card(metadata, accuracy), encoding="utf-8"
    )
    return checksum, metadata, accuracy, operational


def test_verifies_exact_release_evidence_bundle(tmp_path) -> None:
    checksum, _, _, _ = _write_bundle(tmp_path)

    manifest = verify_release_bundle(
        tmp_path,
        expected_model_version="release-1",
        expected_model_sha256=checksum,
    )

    assert manifest == {
        "schema_version": "nailsize-model-release@1",
        "model_version": "release-1",
        "model_sha256": checksum,
        "dataset_version": "holdout-1",
        "segmentation_boundary_error_px": 0.8,
        "accuracy_participant_count": 200,
        "accuracy_nail_count": 2000,
        "operational_participant_count": 200,
        "approved": True,
    }


def test_rejects_missing_unexpected_and_synthetic_release_inputs(tmp_path) -> None:
    checksum, _, _, _ = _write_bundle(tmp_path)
    (tmp_path / "unexpected.txt").write_text("no", encoding="utf-8")
    with pytest.raises(ValueError, match="files do not match"):
        verify_release_bundle(
            tmp_path, expected_model_version="release-1", expected_model_sha256=checksum
        )
    (tmp_path / "unexpected.txt").unlink()
    with pytest.raises(ValueError, match="non-synthetic"):
        verify_release_bundle(
            tmp_path,
            expected_model_version="synthetic-release",
            expected_model_sha256=checksum,
        )
    with pytest.raises(ValueError, match="approved checksum"):
        verify_release_bundle(
            tmp_path, expected_model_version="release-1", expected_model_sha256="0" * 64
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda report: report.update(passed=False), "must pass"),
        (lambda report: report.update(participant_count=199), "at least 200"),
        (
            lambda report: report["metrics"].update(first_pass_completion_rate=0.84),
            "First-pass",
        ),
        (lambda report: report.update(repeatability_review_ref=""), "repeatability review"),
        (lambda report: report.update(adequately_sampled_cohorts=[]), "reviewed cohorts"),
    ],
)
def test_rejects_tampered_operational_evidence(tmp_path, mutation, message: str) -> None:
    checksum, _, _, operational = _write_bundle(tmp_path)
    tampered = deepcopy(operational)
    mutation(tampered)
    (tmp_path / "operational-report.json").write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        verify_release_bundle(
            tmp_path, expected_model_version="release-1", expected_model_sha256=checksum
        )


def test_rejects_modified_model_card_and_nonpositive_boundary_error(tmp_path) -> None:
    checksum, metadata, accuracy, _ = _write_bundle(tmp_path)
    (tmp_path / "model-card.md").write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError, match="does not exactly match"):
        verify_release_bundle(
            tmp_path, expected_model_version="release-1", expected_model_sha256=checksum
        )

    metadata["segmentation_metrics"]["p95_boundary_error_px"] = 0
    (tmp_path / "model-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (tmp_path / "model-card.md").write_text(render_model_card(metadata, accuracy), encoding="utf-8")
    with pytest.raises(ValueError, match="greater than zero"):
        verify_release_bundle(
            tmp_path, expected_model_version="release-1", expected_model_sha256=checksum
        )


def test_rejects_tampered_accuracy_metrics_despite_passing_flags(tmp_path) -> None:
    checksum, metadata, accuracy, _ = _write_bundle(tmp_path)
    accuracy["overall"]["metrics"]["width_mae_mm"] = 0.61
    (tmp_path / "accuracy-report.json").write_text(json.dumps(accuracy), encoding="utf-8")
    (tmp_path / "model-card.md").write_text(render_model_card(metadata, accuracy), encoding="utf-8")

    with pytest.raises(ValueError, match="Width MAE"):
        verify_release_bundle(
            tmp_path, expected_model_version="release-1", expected_model_sha256=checksum
        )
