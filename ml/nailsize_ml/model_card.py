import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

from .reporting import METRIC_NAMES, REQUIRED_COHORT_DIMENSIONS

REQUIRED_APPROVALS = ("model_owner", "nail_tech", "privacy_security")
SEGMENTATION_METRICS = (
    "iou",
    "dice",
    "mean_boundary_error_px",
    "p95_boundary_error_px",
)


def render_model_card(metadata: dict[str, Any], accuracy_report: dict[str, Any]) -> str:
    _validate_release_evidence(metadata, accuracy_report)
    overall = accuracy_report["overall"]
    metrics = overall["metrics"]
    intervals = overall["confidence_intervals_95"]
    segmentation = metadata["segmentation_metrics"]
    approvals = metadata["approvals"]

    lines = [
        f"# {metadata['model_name']} Model Card",
        "",
        f"- Model version: `{metadata['model_version']}`",
        f"- Model SHA-256: `{metadata['model_sha256']}`",
        f"- Dataset version: `{metadata['dataset_version']}`",
        f"- Holdout: {accuracy_report['participant_count']} participants / "
        f"{accuracy_report['nail_count']} nails",
        "",
        "## Intended use",
        "",
        metadata["intended_use"],
        "",
        "## Out of scope",
        "",
        *[f"- {item}" for item in metadata["out_of_scope"]],
        "",
        "## Segmentation and export validation",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        *[f"| {name} | {segmentation[name]:.6g} |" for name in SEGMENTATION_METRICS],
        f"| ONNX maximum absolute parity error | {metadata['onnx_parity_max_abs_error']:.6g} |",
        "",
        "## Participant-disjoint holdout accuracy",
        "",
        "| Metric | Estimate | Participant-clustered 95% CI |",
        "| --- | ---: | ---: |",
        *[
            f"| {name} | {metrics[name]:.6g} | "
            f"{intervals[name]['lower']:.6g}–{intervals[name]['upper']:.6g} |"
            for name in METRIC_NAMES
        ],
        "",
        "## Adequately sampled cohorts",
        "",
        "| Dimension | Cohort | Participants | Nails | MAE (mm) | Exact size | Passed |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
        *[
            f"| {item['dimension']} | {item['value']} | {item['participant_count']} | "
            f"{item['nail_count']} | {item['metrics']['width_mae_mm']:.3f} | "
            f"{item['metrics']['exact_size_rate']:.1%} | {'yes' if item['passed'] else 'no'} |"
            for item in accuracy_report["adequately_sampled_cohorts"]
        ],
        "",
        "## Limitations",
        "",
        *[f"- {item}" for item in metadata["limitations"]],
        "",
        "## Release reviews",
        "",
        *[f"- {name.replace('_', ' ').title()}: {approvals[name]}" for name in REQUIRED_APPROVALS],
        "",
    ]
    return "\n".join(lines)


def _validate_release_evidence(metadata: dict[str, Any], accuracy_report: dict[str, Any]) -> None:
    if accuracy_report.get("schema_version") != "nailsize-accuracy-report@1":
        raise ValueError("Unsupported accuracy report schema")
    if accuracy_report.get("passed") is not True:
        raise ValueError("Accuracy report must pass before publishing a model card")
    dataset_checks = accuracy_report.get("dataset_checks")
    if (
        not isinstance(dataset_checks, dict)
        or not dataset_checks
        or not all(value is True for value in dataset_checks.values())
    ):
        raise ValueError("Accuracy report dataset checks must all pass")
    overall = accuracy_report.get("overall")
    if not isinstance(overall, dict) or overall.get("passed") is not True:
        raise ValueError("Accuracy report overall gates must pass")
    cohorts = accuracy_report.get("adequately_sampled_cohorts")
    if not isinstance(cohorts, list) or not cohorts:
        raise ValueError("Model card requires adequately sampled cohort results")
    if any(not isinstance(item, dict) or item.get("passed") is not True for item in cohorts):
        raise ValueError("Every published cohort must pass")
    if not REQUIRED_COHORT_DIMENSIONS.issubset({item.get("dimension") for item in cohorts}):
        raise ValueError("Model card requires every planned cohort dimension")

    for field in ("model_name", "model_version", "dataset_version", "intended_use"):
        _required_text(metadata, field)
    checksum = _required_text(metadata, "model_sha256")
    if re.fullmatch(r"[0-9a-f]{64}", checksum) is None:
        raise ValueError("model_sha256 must be a lowercase SHA-256 digest")
    for field in ("out_of_scope", "limitations"):
        values = metadata.get(field)
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) or not value.strip() for value in values)
        ):
            raise ValueError(f"{field} must contain non-empty text entries")

    segmentation = metadata.get("segmentation_metrics")
    if not isinstance(segmentation, dict):
        raise ValueError("segmentation_metrics is required")
    for name in SEGMENTATION_METRICS:
        value = _finite_number(segmentation.get(name), name)
        if value < 0 or (name in {"iou", "dice"} and value > 1):
            raise ValueError(f"Invalid segmentation metric: {name}")
    parity = _finite_number(metadata.get("onnx_parity_max_abs_error"), "onnx_parity_max_abs_error")
    if parity < 0 or parity > 1e-4:
        raise ValueError("ONNX parity error must be between 0 and 1e-4")

    approvals = metadata.get("approvals")
    if not isinstance(approvals, dict):
        raise ValueError("approvals is required")
    for name in REQUIRED_APPROVALS:
        _required_text(approvals, name)


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    return float(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a validated NailSize model card")
    parser.add_argument("metadata", type=Path)
    parser.add_argument("accuracy_report", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    metadata = json.loads(arguments.metadata.read_text(encoding="utf-8"))
    report = json.loads(arguments.accuracy_report.read_text(encoding="utf-8"))
    arguments.output.write_text(render_model_card(metadata, report), encoding="utf-8")


if __name__ == "__main__":
    main()
