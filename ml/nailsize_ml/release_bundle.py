import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .model_card import render_model_card
from .operational_validation import OPERATIONAL_METRICS
from .reporting import METRIC_NAMES, REQUIRED_COHORT_DIMENSIONS

REQUIRED_FILENAMES = frozenset(
    {
        "accuracy-report.json",
        "annotation-agreement-report.json",
        "model-card.md",
        "model-metadata.json",
        "nail-segmentation.onnx",
        "onnx-export-report.json",
        "operational-report.json",
    }
)
ANNOTATION_METRICS = (
    "item_count",
    "mean_mask_dice",
    "mean_boundary_distance_normalized",
    "digit_agreement",
    "quality_code_agreement",
    "best_fit_agreement",
    "best_fit_kappa",
    "mean_width_difference_mm",
)
ANNOTATION_REPORT_FIELDS = frozenset(
    {
        "schema_version",
        "dataset_version",
        "total_annotated_item_count",
        "paired_item_count",
        "paired_participant_count",
        "double_annotation_rate",
        "metrics",
        "disagreement_counts",
        "required_adjudication_count",
        "completed_adjudication_count",
        "dataset_checks",
        "agreement_review_ref",
        "adjudication_review_ref",
        "passed",
    }
)
EXPORT_REPORT_FIELDS = frozenset(
    {
        "architecture",
        "checkpoint_sha256",
        "checkpoint_torch_version",
        "final_training_loss",
        "input_shape",
        "model_sha256",
        "model_version",
        "output_shape",
        "parity_max_abs_error",
        "parity_tolerance",
        "provider",
        "schema_version",
        "training_epochs",
        "training_examples",
    }
)
REJECTED_VERSION_MARKERS = (
    "contract",
    "fixture",
    "placeholder",
    "synthetic",
    "test-model",
    "unavailable",
)


def verify_release_bundle(
    bundle_directory: str | Path,
    *,
    expected_model_version: str,
    expected_model_sha256: str,
) -> dict[str, Any]:
    directory = Path(bundle_directory)
    if not directory.is_dir():
        raise ValueError("Release bundle directory does not exist")
    present = {path.name for path in directory.iterdir() if path.is_file()}
    if present != REQUIRED_FILENAMES:
        missing = sorted(REQUIRED_FILENAMES - present)
        unexpected = sorted(present - REQUIRED_FILENAMES)
        raise ValueError(
            "Release bundle files do not match contract; "
            f"missing={missing}, unexpected={unexpected}"
        )
    if not expected_model_version.strip() or any(
        marker in expected_model_version.lower() for marker in REJECTED_VERSION_MARKERS
    ):
        raise ValueError("A non-synthetic immutable model version is required")
    if len(expected_model_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in expected_model_sha256
    ):
        raise ValueError("Expected model SHA-256 must be 64 lowercase hexadecimal characters")

    metadata = _read_json(directory / "model-metadata.json")
    accuracy = _read_json(directory / "accuracy-report.json")
    annotation_agreement = _read_json(directory / "annotation-agreement-report.json")
    export_report = _read_json(directory / "onnx-export-report.json")
    operational = _read_json(directory / "operational-report.json")
    model_path = directory / "nail-segmentation.onnx"
    actual_sha256 = _sha256(model_path)

    if metadata.get("model_version") != expected_model_version:
        raise ValueError("Model metadata version does not match the approved version")
    if metadata.get("model_sha256") != expected_model_sha256:
        raise ValueError("Model metadata checksum does not match the approved checksum")
    if actual_sha256 != expected_model_sha256:
        raise ValueError("ONNX file checksum does not match the approved checksum")

    checkpoint_sha256, parity_error = _validate_export_report(
        export_report,
        metadata=metadata,
        expected_model_version=expected_model_version,
        expected_model_sha256=expected_model_sha256,
    )

    rendered_card = render_model_card(metadata, accuracy)
    committed_card = (directory / "model-card.md").read_text(encoding="utf-8")
    if committed_card.rstrip("\n") != rendered_card.rstrip("\n"):
        raise ValueError("Model card does not exactly match the validated release evidence")

    _validate_accuracy_report(accuracy)
    _validate_annotation_agreement_report(
        annotation_agreement, expected_dataset_version=metadata["dataset_version"]
    )
    _validate_operational_report(operational)
    segmentation = metadata["segmentation_metrics"]
    boundary_error = _positive_finite(
        segmentation.get("p95_boundary_error_px"), "p95_boundary_error_px"
    )
    return {
        "schema_version": "nailsize-model-release@3",
        "checkpoint_sha256": checkpoint_sha256,
        "model_version": expected_model_version,
        "model_sha256": expected_model_sha256,
        "onnx_parity_max_abs_error": parity_error,
        "dataset_version": metadata["dataset_version"],
        "segmentation_boundary_error_px": boundary_error,
        "accuracy_participant_count": accuracy["participant_count"],
        "accuracy_nail_count": accuracy["nail_count"],
        "annotation_paired_item_count": annotation_agreement["paired_item_count"],
        "annotation_paired_participant_count": annotation_agreement["paired_participant_count"],
        "operational_participant_count": operational["participant_count"],
        "approved": True,
    }


def _validate_export_report(
    report: dict[str, Any],
    *,
    metadata: dict[str, Any],
    expected_model_version: str,
    expected_model_sha256: str,
) -> tuple[str, float]:
    if frozenset(report) != EXPORT_REPORT_FIELDS:
        raise ValueError("Selected-checkpoint export report fields do not match contract")
    if report.get("schema_version") != "nailsize-selected-checkpoint-export@1":
        raise ValueError("Unsupported selected-checkpoint export report schema")
    if report.get("architecture") != "deeplabv3_mobilenet_v3_large":
        raise ValueError("Selected-checkpoint architecture does not match production")

    checkpoint_sha256 = report.get("checkpoint_sha256")
    if not isinstance(checkpoint_sha256, str) or not _valid_sha256(checkpoint_sha256):
        raise ValueError("Selected-checkpoint SHA-256 must be lowercase hexadecimal")
    if report.get("model_version") != expected_model_version:
        raise ValueError("Export report version does not match the approved version")
    if report.get("model_sha256") != expected_model_sha256:
        raise ValueError("Export report checksum does not match the approved checksum")
    if report.get("provider") != "CPUExecutionProvider":
        raise ValueError("Selected-checkpoint export must use CPUExecutionProvider")
    if report.get("input_shape") != [1, 3, 224, 160]:
        raise ValueError("Selected-checkpoint export input shape does not match production")
    if report.get("output_shape") != [1, 1, 224, 160]:
        raise ValueError("Selected-checkpoint export output shape does not match production")

    parity_error = _finite(report.get("parity_max_abs_error"), "parity_max_abs_error")
    parity_tolerance = _positive_finite(report.get("parity_tolerance"), "parity_tolerance")
    if parity_error < 0:
        raise ValueError("parity_max_abs_error must not be negative")
    if parity_tolerance > 1e-4:
        raise ValueError("Selected-checkpoint parity tolerance exceeds the release ceiling")
    if parity_error > parity_tolerance:
        raise ValueError("Selected-checkpoint parity error exceeds its verified tolerance")
    metadata_parity = _finite(
        metadata.get("onnx_parity_max_abs_error"), "metadata onnx_parity_max_abs_error"
    )
    if metadata_parity != parity_error:
        raise ValueError("Model metadata parity does not match selected-checkpoint export evidence")

    _positive_integer(report.get("training_examples"), "training_examples")
    _positive_integer(report.get("training_epochs"), "training_epochs")
    final_loss = _finite(report.get("final_training_loss"), "final_training_loss")
    if final_loss < 0:
        raise ValueError("final_training_loss must not be negative")
    torch_version = report.get("checkpoint_torch_version")
    if not isinstance(torch_version, str) or not torch_version.strip():
        raise ValueError("Selected-checkpoint PyTorch version is required")
    return checkpoint_sha256, parity_error


def _validate_accuracy_report(report: dict[str, Any]) -> None:
    if report.get("schema_version") != "nailsize-accuracy-report@1":
        raise ValueError("Unsupported accuracy report schema")
    if report.get("passed") is not True:
        raise ValueError("Accuracy report must pass before release")
    if report.get("participant_count", 0) < 200 or report.get("nail_count", 0) < 2_000:
        raise ValueError("Accuracy report requires at least 200 participants and 2,000 nails")
    _all_checks_pass(report.get("dataset_checks"), "Accuracy report dataset checks")
    overall = report.get("overall")
    if not isinstance(overall, dict) or overall.get("passed") is not True:
        raise ValueError("Accuracy report overall gates must pass")
    _all_checks_pass(overall.get("checks"), "Accuracy report overall checks")
    metrics = overall.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("Accuracy report overall metrics are required")
    values = {name: _finite(metrics.get(name), name) for name in METRIC_NAMES}
    if values["width_mae_mm"] > 0.6:
        raise ValueError("Width MAE gate failed")
    if values["width_p90_error_mm"] > 1.0:
        raise ValueError("Width p90 gate failed")
    if abs(values["signed_bias_mm"]) > 0.2:
        raise ValueError("Signed bias gate failed")
    if values["exact_size_rate"] < 0.90:
        raise ValueError("Exact-size gate failed")
    if values["exact_or_adjacent_rate"] < 0.99:
        raise ValueError("Exact-or-adjacent gate failed")
    if values["more_than_one_size_miss_rate"] > 0.01:
        raise ValueError("Severe size-miss gate failed")
    _validate_intervals(overall.get("confidence_intervals_95"), METRIC_NAMES, "accuracy")

    cohorts = report.get("adequately_sampled_cohorts")
    if not isinstance(cohorts, list) or not cohorts:
        raise ValueError("Accuracy report requires reviewed cohorts")
    for cohort in cohorts:
        if not isinstance(cohort, dict) or cohort.get("passed") is not True:
            raise ValueError("Every accuracy cohort must pass")
        if cohort.get("participant_count", 0) <= 0 or cohort.get("nail_count", 0) <= 0:
            raise ValueError("Every accuracy cohort requires positive study counts")
        _all_checks_pass(cohort.get("checks"), "Accuracy cohort checks")
        cohort_metrics = cohort.get("metrics")
        if not isinstance(cohort_metrics, dict):
            raise ValueError("Accuracy cohort metrics are required")
        cohort_mae = _finite(cohort_metrics.get("width_mae_mm"), "cohort width_mae_mm")
        cohort_exact = _finite(cohort_metrics.get("exact_size_rate"), "cohort exact_size_rate")
        if cohort_mae > 0.85 or cohort_exact < values["exact_size_rate"] - 0.05:
            raise ValueError("Accuracy cohort numeric gate failed")
    if not REQUIRED_COHORT_DIMENSIONS.issubset({item.get("dimension") for item in cohorts}):
        raise ValueError("Accuracy report requires every planned cohort dimension")


def _validate_annotation_agreement_report(
    report: dict[str, Any], *, expected_dataset_version: str
) -> None:
    if frozenset(report) != ANNOTATION_REPORT_FIELDS:
        raise ValueError("Annotation agreement report fields do not match the contract")
    if report.get("schema_version") != "nailsize-annotation-agreement-report@1":
        raise ValueError("Unsupported annotation agreement report schema")
    if report.get("passed") is not True:
        raise ValueError("Annotation agreement report must pass before release")
    if report.get("dataset_version") != expected_dataset_version:
        raise ValueError("Annotation agreement dataset does not match model metadata")
    total = _positive_integer(
        report.get("total_annotated_item_count"), "total_annotated_item_count"
    )
    paired = _positive_integer(report.get("paired_item_count"), "paired_item_count")
    paired_participants = _positive_integer(
        report.get("paired_participant_count"), "paired_participant_count"
    )
    if paired > total or paired_participants > paired:
        raise ValueError("Annotation paired counts exceed the dataset item counts")
    double_annotation_rate = _finite(report.get("double_annotation_rate"), "double_annotation_rate")
    if not 0.10 <= double_annotation_rate <= 1 or double_annotation_rate != paired / total:
        raise ValueError("Annotation double-annotation coverage must be at least 10% and exact")
    dataset_checks = report.get("dataset_checks")
    expected_checks = {
        "minimum_double_annotation_rate",
        "two_independent_technicians",
        "agreement_review_present",
        "adjudication_review_present",
        "material_disagreements_adjudicated",
    }
    if not isinstance(dataset_checks, dict) or set(dataset_checks) != expected_checks:
        raise ValueError("Annotation agreement dataset checks do not match the contract")
    _all_checks_pass(dataset_checks, "Annotation agreement dataset checks")
    metrics = report.get("metrics")
    if not isinstance(metrics, dict) or set(metrics) != set(ANNOTATION_METRICS):
        raise ValueError("Annotation agreement metrics do not match the contract")
    values = {name: _finite(metrics.get(name), name) for name in ANNOTATION_METRICS}
    if values["item_count"] != paired:
        raise ValueError("Annotation metric item count does not match paired item count")
    for name in (
        "mean_mask_dice",
        "digit_agreement",
        "quality_code_agreement",
        "best_fit_agreement",
    ):
        if not 0 <= values[name] <= 1:
            raise ValueError(f"Annotation agreement metric is outside [0, 1]: {name}")
    if not -1 <= values["best_fit_kappa"] <= 1:
        raise ValueError("Annotation best-fit kappa is outside [-1, 1]")
    if values["mean_boundary_distance_normalized"] < 0 or values["mean_width_difference_mm"] < 0:
        raise ValueError("Annotation distance metrics must not be negative")
    required = report.get("required_adjudication_count")
    completed = report.get("completed_adjudication_count")
    if (
        isinstance(required, bool)
        or not isinstance(required, int)
        or required < 0
        or isinstance(completed, bool)
        or not isinstance(completed, int)
        or completed < required
        or completed > paired
    ):
        raise ValueError("Annotation material disagreements must be fully adjudicated")
    disagreements = report.get("disagreement_counts")
    expected_disagreements = {
        "digit",
        "quality_codes",
        "best_fit_size",
        "physical_width_over_0_5_mm",
        "disputed_boundary",
    }
    if (
        not isinstance(disagreements, dict)
        or set(disagreements) != expected_disagreements
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in disagreements.values()
        )
    ):
        raise ValueError("Annotation disagreement counts do not match the contract")
    for field in ("agreement_review_ref", "adjudication_review_ref"):
        if not isinstance(report.get(field), str) or not report[field].strip():
            raise ValueError("Annotation agreement requires named review references")


def _validate_operational_report(report: dict[str, Any]) -> None:
    if report.get("schema_version") != "nailsize-operational-report@1":
        raise ValueError("Unsupported operational report schema")
    if report.get("passed") is not True:
        raise ValueError("Operational report must pass before release")
    if report.get("participant_count", 0) < 200:
        raise ValueError("Operational report requires at least 200 participants")
    for field in ("dataset_checks", "gate_checks"):
        _all_checks_pass(report.get(field), f"Operational report {field}")
    metrics = report.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("Operational report metrics are required")
    for metric in OPERATIONAL_METRICS:
        _finite(metrics.get(metric), metric)
    _validate_intervals(report.get("confidence_intervals_95"), OPERATIONAL_METRICS, "operational")
    if metrics["first_pass_completion_rate"] < 0.85:
        raise ValueError("First-pass completion gate failed")
    if metrics["after_one_retake_completion_rate"] < 0.95:
        raise ValueError("One-retake completion gate failed")
    if metrics["invalid_false_acceptance_rate"] > 0.02:
        raise ValueError("Invalid false-acceptance gate failed")
    if metrics["valid_false_rejection_rate"] > 0.10:
        raise ValueError("Valid false-rejection gate failed")
    if (
        not isinstance(report.get("repeatability_review_ref"), str)
        or not report["repeatability_review_ref"].strip()
    ):
        raise ValueError("Operational report requires a repeatability review")
    cohorts = report.get("adequately_sampled_cohorts")
    if not isinstance(cohorts, list) or not cohorts:
        raise ValueError("Operational report requires reviewed cohorts")
    if any(
        not isinstance(item, dict)
        or item.get("passed") is not True
        or item.get("participant_count", 0) <= 0
        or item.get("decision_count", 0) <= 0
        or not isinstance(item.get("parity_review_ref"), str)
        or not item["parity_review_ref"].strip()
        for item in cohorts
    ):
        raise ValueError("Every operational cohort requires a passing parity review")
    if not REQUIRED_COHORT_DIMENSIONS.issubset({item.get("dimension") for item in cohorts}):
        raise ValueError("Operational report requires every planned cohort dimension")


def _all_checks_pass(checks: Any, label: str) -> None:
    if (
        not isinstance(checks, dict)
        or not checks
        or not all(value is True for value in checks.values())
    ):
        raise ValueError(f"{label} must all pass")


def _validate_intervals(intervals: Any, metrics: tuple[str, ...], label: str) -> None:
    if not isinstance(intervals, dict):
        raise ValueError(f"{label.title()} confidence intervals are required")
    for metric in metrics:
        interval = intervals.get(metric)
        if not isinstance(interval, dict):
            raise ValueError(f"{label.title()} confidence interval missing for {metric}")
        lower = _finite(interval.get("lower"), f"{metric} interval lower")
        upper = _finite(interval.get("upper"), f"{metric} interval upper")
        if lower > upper:
            raise ValueError(f"{label.title()} confidence interval is inverted for {metric}")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid release JSON: {path.name}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"Release JSON must be an object: {path.name}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    return float(value)


def _positive_finite(value: Any, field: str) -> float:
    numeric = _finite(value, field)
    if numeric <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return numeric


def _positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a production model release bundle")
    parser.add_argument("bundle_directory", type=Path)
    parser.add_argument("--expected-model-version", required=True)
    parser.add_argument("--expected-model-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    manifest = verify_release_bundle(
        arguments.bundle_directory,
        expected_model_version=arguments.expected_model_version,
        expected_model_sha256=arguments.expected_model_sha256,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
