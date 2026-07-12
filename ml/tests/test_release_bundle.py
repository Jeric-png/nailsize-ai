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


def _export_report(checksum: str) -> dict:
    return {
        "schema_version": "nailsize-selected-checkpoint-export@1",
        "architecture": "deeplabv3_mobilenet_v3_large",
        "checkpoint_sha256": "a" * 64,
        "model_sha256": checksum,
        "model_version": "release-1",
        "training_examples": 2400,
        "training_epochs": 12,
        "final_training_loss": 0.08,
        "parity_max_abs_error": 0.00001,
        "parity_tolerance": 0.0001,
        "input_shape": [1, 3, 224, 160],
        "output_shape": [1, 1, 224, 160],
        "provider": "CPUExecutionProvider",
        "checkpoint_torch_version": "2.8.0",
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


def _annotation_agreement_report() -> dict:
    return {
        "schema_version": "nailsize-annotation-agreement-report@1",
        "dataset_version": "holdout-1",
        "total_annotated_item_count": 2000,
        "paired_item_count": 200,
        "paired_participant_count": 40,
        "double_annotation_rate": 0.1,
        "metrics": {
            "item_count": 200,
            "mean_mask_dice": 0.94,
            "mean_boundary_distance_normalized": 0.01,
            "digit_agreement": 0.99,
            "quality_code_agreement": 0.95,
            "best_fit_agreement": 0.91,
            "best_fit_kappa": 0.89,
            "mean_width_difference_mm": 0.2,
        },
        "disagreement_counts": {
            "digit": 2,
            "quality_codes": 10,
            "best_fit_size": 18,
            "physical_width_over_0_5_mm": 4,
            "disputed_boundary": 3,
        },
        "required_adjudication_count": 25,
        "completed_adjudication_count": 25,
        "dataset_checks": {
            "minimum_double_annotation_rate": True,
            "two_independent_technicians": True,
            "agreement_review_present": True,
            "adjudication_review_present": True,
            "material_disagreements_adjudicated": True,
        },
        "agreement_review_ref": "agreement-review-1",
        "adjudication_review_ref": "adjudication-review-1",
        "passed": True,
    }


def _size_calibration_report() -> dict:
    metrics = {
        "exact_size_rate": 0.92,
        "exact_or_adjacent_rate": 0.995,
        "more_than_one_size_miss_rate": 0.005,
        "unmappable_rate": 0.0,
        "mean_best_fit_tip_margin_mm": 0.2,
        "p90_absolute_best_fit_tip_margin_mm": 0.5,
    }
    return {
        "schema_version": "nailsize-size-calibration-report@1",
        "dataset_version": "holdout-1",
        "chart_id": "platform-default",
        "chart_version": "1",
        "participant_count": 200,
        "nail_count": 2000,
        "metrics": metrics,
        "confidence_intervals_95": {
            name: {
                "lower": max(0.0, value - 0.01) if "rate" in name else value - 0.01,
                "upper": min(1.0, value + 0.01) if "rate" in name else value + 0.01,
            }
            for name, value in metrics.items()
        },
        "dataset_checks": {
            "minimum_participants": True,
            "minimum_nails": True,
            "all_widths_mappable": True,
            "curvature_reviews_present": True,
        },
        "gate_checks": {
            "exact_size_rate": True,
            "exact_or_adjacent_rate": True,
            "more_than_one_size_miss_rate": True,
            "calibration_review_present": True,
        },
        "adequately_sampled_curvature_cohorts": [
            {
                "cohort": "medium",
                "participant_count": 100,
                "nail_count": 1000,
                "metrics": metrics,
                "checks": {"exact_size_rate_gap": True, "review_present": True},
                "review_ref": "curvature-review-1",
                "passed": True,
            }
        ],
        "calibration_review_ref": "calibration-review-1",
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
    export = _export_report(checksum)
    accuracy = _accuracy_report()
    annotation_agreement = _annotation_agreement_report()
    operational = _operational_report()
    size_calibration = _size_calibration_report()
    (directory / "model-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (directory / "onnx-export-report.json").write_text(json.dumps(export), encoding="utf-8")
    (directory / "accuracy-report.json").write_text(json.dumps(accuracy), encoding="utf-8")
    (directory / "annotation-agreement-report.json").write_text(
        json.dumps(annotation_agreement), encoding="utf-8"
    )
    (directory / "operational-report.json").write_text(json.dumps(operational), encoding="utf-8")
    (directory / "size-calibration-report.json").write_text(
        json.dumps(size_calibration), encoding="utf-8"
    )
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
        "schema_version": "nailsize-model-release@4",
        "checkpoint_sha256": "a" * 64,
        "model_version": "release-1",
        "model_sha256": checksum,
        "onnx_parity_max_abs_error": 0.00001,
        "dataset_version": "holdout-1",
        "chart_id": "platform-default",
        "chart_version": "1",
        "segmentation_boundary_error_px": 0.8,
        "accuracy_participant_count": 200,
        "accuracy_nail_count": 2000,
        "annotation_paired_item_count": 200,
        "annotation_paired_participant_count": 40,
        "size_calibration_participant_count": 200,
        "size_calibration_nail_count": 2000,
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
    export_report = tmp_path / "onnx-export-report.json"
    export_report.unlink()
    with pytest.raises(ValueError, match="files do not match"):
        verify_release_bundle(
            tmp_path, expected_model_version="release-1", expected_model_sha256=checksum
        )
    export_report.write_text(json.dumps(_export_report(checksum)), encoding="utf-8")
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
    ("field", "value", "message"),
    [
        ("schema_version", "unknown@1", "schema"),
        ("architecture", "other", "architecture"),
        ("checkpoint_sha256", "0", "checkpoint SHA-256"),
        ("model_version", "release-2", "version"),
        ("model_sha256", "b" * 64, "checksum"),
        ("provider", "CUDAExecutionProvider", "CPUExecutionProvider"),
        ("input_shape", [1, 3, 160, 224], "input shape"),
        ("output_shape", [1, 1, 160, 224], "output shape"),
        ("parity_max_abs_error", -0.1, "must not be negative"),
        ("parity_tolerance", 0.001, "release ceiling"),
        ("training_examples", 0, "positive integer"),
        ("training_epochs", True, "positive integer"),
        ("final_training_loss", -0.1, "must not be negative"),
        ("checkpoint_torch_version", "", "PyTorch version"),
    ],
)
def test_rejects_tampered_selected_checkpoint_export_evidence(
    tmp_path, field: str, value, message: str
) -> None:
    checksum, _, _, _ = _write_bundle(tmp_path)
    report_path = tmp_path / "onnx-export-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report[field] = value
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        verify_release_bundle(
            tmp_path, expected_model_version="release-1", expected_model_sha256=checksum
        )


def test_rejects_parity_not_linked_to_export_or_outside_export_tolerance(tmp_path) -> None:
    checksum, metadata, accuracy, _ = _write_bundle(tmp_path)
    metadata["onnx_parity_max_abs_error"] = 0.00002
    (tmp_path / "model-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (tmp_path / "model-card.md").write_text(render_model_card(metadata, accuracy), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match selected-checkpoint"):
        verify_release_bundle(
            tmp_path, expected_model_version="release-1", expected_model_sha256=checksum
        )

    metadata["onnx_parity_max_abs_error"] = 0.00001
    (tmp_path / "model-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (tmp_path / "model-card.md").write_text(render_model_card(metadata, accuracy), encoding="utf-8")
    report_path = tmp_path / "onnx-export-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["parity_tolerance"] = 0.000001
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="exceeds its verified tolerance"):
        verify_release_bundle(
            tmp_path, expected_model_version="release-1", expected_model_sha256=checksum
        )


def test_rejects_added_export_report_fields(tmp_path) -> None:
    checksum, _, _, _ = _write_bundle(tmp_path)
    report_path = tmp_path / "onnx-export-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["unreviewed"] = True
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="fields do not match"):
        verify_release_bundle(
            tmp_path, expected_model_version="release-1", expected_model_sha256=checksum
        )


def test_rejects_removed_export_report_fields(tmp_path) -> None:
    checksum, _, _, _ = _write_bundle(tmp_path)
    report_path = tmp_path / "onnx-export-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    del report["training_epochs"]
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="fields do not match"):
        verify_release_bundle(
            tmp_path, expected_model_version="release-1", expected_model_sha256=checksum
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


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda report: report.update(passed=False), "must pass"),
        (lambda report: report.update(dataset_version="other"), "does not match"),
        (lambda report: report.update(double_annotation_rate=0.099), "at least 10%"),
        (lambda report: report.update(completed_adjudication_count=24), "fully adjudicated"),
        (lambda report: report.update(agreement_review_ref=""), "named review"),
        (lambda report: report.update(image_ids=["private-image"]), "fields do not match"),
    ],
)
def test_rejects_tampered_annotation_agreement_evidence(tmp_path, mutation, message: str) -> None:
    checksum, _, _, _ = _write_bundle(tmp_path)
    report_path = tmp_path / "annotation-agreement-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    mutation(report)
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        verify_release_bundle(
            tmp_path, expected_model_version="release-1", expected_model_sha256=checksum
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda report: report.update(passed=False), "must pass"),
        (lambda report: report.update(dataset_version="other"), "does not match"),
        (lambda report: report.update(chart_version="2"), "does not match production"),
        (lambda report: report.update(nail_count=1999), "do not match the accuracy"),
        (lambda report: report["metrics"].update(exact_size_rate=0.89), "exact-size"),
        (lambda report: report["metrics"].update(unmappable_rate=0.01), "unmappable"),
        (
            lambda report: report["adequately_sampled_curvature_cohorts"][0]["metrics"].update(
                exact_size_rate=0.80
            ),
            "cohort exact-size gap",
        ),
        (lambda report: report.update(calibration_review_ref=""), "review is required"),
        (
            lambda report: report["confidence_intervals_95"].update(private_metric={}),
            "confidence intervals do not match",
        ),
        (
            lambda report: report["confidence_intervals_95"]["exact_size_rate"].update(lower=-0.1),
            "outside",
        ),
        (lambda report: report.update(image_ids=["private"]), "fields do not match"),
    ],
)
def test_rejects_tampered_size_calibration_evidence(tmp_path, mutation, message: str) -> None:
    checksum, _, _, _ = _write_bundle(tmp_path)
    report_path = tmp_path / "size-calibration-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    mutation(report)
    report_path.write_text(json.dumps(report), encoding="utf-8")

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
