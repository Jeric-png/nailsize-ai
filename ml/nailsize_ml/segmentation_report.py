import argparse
import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .annotation_report import MAX_MASK_FILE_BYTES, MAX_MASK_PIXELS
from .evaluation import SegmentationMetrics, segmentation_metrics
from .holdout_lock import HOLDOUT_PURPOSE, SPLIT_STRATEGY, SPLIT_THRESHOLDS, holdout_set_commitment
from .holdout_lock import REPORT_FIELDS as HOLDOUT_LOCK_FIELDS
from .holdout_lock import SCHEMA_VERSION as HOLDOUT_LOCK_SCHEMA

SCHEMA_VERSION = "nailsize-segmentation-evaluation-report@1"
METRIC_NAMES = ("iou", "dice", "mean_boundary_error_px", "p95_boundary_error_px")
REPORT_FIELDS = frozenset(
    {
        "schema_version",
        "dataset_version",
        "model_version",
        "model_sha256",
        "holdout_lock_sha256",
        "test_set_commitment_sha256",
        "participant_count",
        "nail_count",
        "prediction_threshold",
        "threshold_selection_ref",
        "metrics",
        "confidence_intervals_95",
        "dataset_checks",
        "gate_checks",
        "segmentation_review_ref",
        "passed",
    }
)
EXPECTED_MASK_SHAPE = (224, 160)


@dataclass(frozen=True)
class SegmentationObservation:
    participant_id: str
    image_id: str
    prediction_probability_uri: str
    ground_truth_mask_uri: str


@dataclass(frozen=True)
class _EvaluatedObservation:
    participant_id: str
    image_id: str
    metrics: SegmentationMetrics


def build_segmentation_evaluation_report(
    observations: Sequence[SegmentationObservation],
    *,
    prediction_mask_root: str | Path,
    ground_truth_mask_root: str | Path,
    dataset_version: str,
    model_version: str,
    model_sha256: str,
    holdout_lock_path: str | Path,
    expected_holdout_lock_sha256: str,
    prediction_threshold: float,
    threshold_selection_ref: str,
    segmentation_review_ref: str,
    bootstrap_iterations: int = 2_000,
    seed: int = 20260712,
) -> dict[str, Any]:
    records = _validate_observations(observations)
    version = _required_text(dataset_version, "dataset version")
    selected_model_version = _required_text(model_version, "model version")
    threshold_review = _required_text(threshold_selection_ref, "threshold selection review")
    segmentation_review = _required_text(segmentation_review_ref, "segmentation review")
    if not _valid_sha256(model_sha256):
        raise ValueError("Model SHA-256 must be lowercase hexadecimal")
    threshold = _finite(prediction_threshold, "prediction threshold")
    if not 0 < threshold < 1:
        raise ValueError("Prediction threshold must be between zero and one")

    holdout = _load_approved_holdout(
        Path(holdout_lock_path), expected_sha256=expected_holdout_lock_sha256
    )
    if holdout["dataset_version"] != version:
        raise ValueError("Segmentation dataset does not match the approved holdout")
    commitment = holdout_set_commitment((item.participant_id, item.image_id) for item in records)
    participant_count = len({item.participant_id for item in records})
    dataset_checks = {
        "holdout_lock_checksum": True,
        "holdout_commitment_match": commitment == holdout["test_set_commitment_sha256"],
        "holdout_participant_count_match": participant_count == holdout["test_participant_count"],
        "holdout_nail_count_match": len(records) == holdout["test_record_count"],
    }
    if not all(dataset_checks.values()):
        raise ValueError("Segmentation observations do not exactly match the approved holdout")

    evaluated = _evaluate_observations(
        records,
        prediction_root=Path(prediction_mask_root),
        ground_truth_root=Path(ground_truth_mask_root),
        prediction_threshold=threshold,
    )
    metrics = _aggregate_metrics(evaluated)
    finite_metrics = all(math.isfinite(getattr(metrics, name)) for name in METRIC_NAMES)
    gate_checks = {
        "overlap_metrics_reported": finite_metrics
        and 0 <= metrics.iou <= 1
        and 0 <= metrics.dice <= 1,
        "boundary_metrics_reported": finite_metrics
        and metrics.mean_boundary_error_px >= 0
        and metrics.p95_boundary_error_px > 0,
        "threshold_selected_without_public_holdout": bool(threshold_review),
        "segmentation_review_present": bool(segmentation_review),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": version,
        "model_version": selected_model_version,
        "model_sha256": model_sha256,
        "holdout_lock_sha256": expected_holdout_lock_sha256,
        "test_set_commitment_sha256": commitment,
        "participant_count": participant_count,
        "nail_count": len(records),
        "prediction_threshold": threshold,
        "threshold_selection_ref": threshold_review,
        "metrics": asdict(metrics),
        "confidence_intervals_95": _clustered_intervals(
            evaluated, iterations=bootstrap_iterations, seed=seed
        ),
        "dataset_checks": dataset_checks,
        "gate_checks": gate_checks,
        "segmentation_review_ref": segmentation_review,
        "passed": all(dataset_checks.values()) and all(gate_checks.values()),
    }


def load_observations(path: str | Path) -> list[SegmentationObservation]:
    records: list[SegmentationObservation] = []
    expected_fields = {
        "participant_id",
        "image_id",
        "prediction_probability_uri",
        "ground_truth_mask_uri",
    }
    try:
        with Path(path).open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    if not isinstance(payload, dict) or set(payload) != expected_fields:
                        raise TypeError
                    records.append(SegmentationObservation(**payload))
                except (json.JSONDecodeError, TypeError) as error:
                    raise ValueError(
                        f"Invalid segmentation observation on line {line_number}"
                    ) from error
    except OSError as error:
        raise ValueError("Segmentation observations could not be read") from error
    return _validate_observations(records)


def _validate_observations(
    observations: Sequence[SegmentationObservation],
) -> list[SegmentationObservation]:
    records = list(observations)
    if not records:
        raise ValueError("At least one segmentation observation is required")
    seen: set[tuple[str, str]] = set()
    for item in records:
        if not isinstance(item, SegmentationObservation):
            raise ValueError("Segmentation observations must use the typed contract")
        for value in (
            item.participant_id,
            item.image_id,
            item.prediction_probability_uri,
            item.ground_truth_mask_uri,
        ):
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError("Segmentation observation strings must be populated and trimmed")
        identity = (item.participant_id, item.image_id)
        if identity in seen:
            raise ValueError("Segmentation participant/image pairs must be unique")
        seen.add(identity)
    return records


def _evaluate_observations(
    observations: Sequence[SegmentationObservation],
    *,
    prediction_root: Path,
    ground_truth_root: Path,
    prediction_threshold: float,
) -> list[_EvaluatedObservation]:
    evaluated: list[_EvaluatedObservation] = []
    for item in observations:
        probabilities = _load_array(
            prediction_root, item.prediction_probability_uri, probabilities=True
        )
        prediction = np.asarray(probabilities >= prediction_threshold, dtype=np.uint8)
        ground_truth = np.asarray(
            _load_array(ground_truth_root, item.ground_truth_mask_uri, probabilities=False),
            dtype=np.uint8,
        )
        if not prediction.any() or not ground_truth.any():
            raise ValueError("Segmentation evaluation masks must contain a visible nail")
        evaluated.append(
            _EvaluatedObservation(
                participant_id=item.participant_id,
                image_id=item.image_id,
                metrics=segmentation_metrics(prediction, ground_truth),
            )
        )
    return evaluated


def _aggregate_metrics(observations: Sequence[_EvaluatedObservation]) -> SegmentationMetrics:
    return SegmentationMetrics(
        iou=float(np.mean([item.metrics.iou for item in observations])),
        dice=float(np.mean([item.metrics.dice for item in observations])),
        mean_boundary_error_px=float(
            np.mean([item.metrics.mean_boundary_error_px for item in observations])
        ),
        p95_boundary_error_px=float(
            np.quantile([item.metrics.p95_boundary_error_px for item in observations], 0.95)
        ),
    )


def _clustered_intervals(
    observations: Sequence[_EvaluatedObservation], *, iterations: int, seed: int
) -> dict[str, dict[str, float]]:
    if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations < 100:
        raise ValueError("At least 100 bootstrap iterations are required")
    by_participant: dict[str, list[_EvaluatedObservation]] = defaultdict(list)
    for item in observations:
        by_participant[item.participant_id].append(item)
    participant_ids = sorted(by_participant)
    random = np.random.default_rng(seed)
    samples = {name: np.empty(iterations, dtype=float) for name in METRIC_NAMES}
    for index in range(iterations):
        chosen = random.choice(participant_ids, size=len(participant_ids), replace=True)
        sampled = [
            item for participant_id in chosen for item in by_participant[str(participant_id)]
        ]
        metrics = _aggregate_metrics(sampled)
        for name in METRIC_NAMES:
            samples[name][index] = getattr(metrics, name)
    return {
        name: {
            "lower": float(np.quantile(values, 0.025)),
            "upper": float(np.quantile(values, 0.975)),
        }
        for name, values in samples.items()
    }


def _load_array(root: Path, relative_uri: str, *, probabilities: bool) -> NDArray[np.generic]:
    relative = Path(relative_uri)
    if relative.is_absolute() or relative.suffix.lower() != ".npy" or ".." in relative.parts:
        raise ValueError("Mask URIs must be safe relative .npy paths")
    approved_root = root.resolve()
    path = (approved_root / relative).resolve()
    try:
        path.relative_to(approved_root)
    except ValueError as error:
        raise ValueError("Mask URI escapes its approved root") from error
    if not path.is_file() or path.stat().st_size > MAX_MASK_FILE_BYTES:
        raise ValueError("Mask file is missing or exceeds the size limit")
    try:
        mask = np.load(path, allow_pickle=False, mmap_mode="r")
    except (OSError, ValueError) as error:
        raise ValueError("Mask file is not a valid non-pickled NumPy array") from error
    if (
        mask.shape != EXPECTED_MASK_SHAPE
        or mask.size > MAX_MASK_PIXELS
        or mask.dtype.kind not in "biuf"
        or not np.isfinite(mask).all()
    ):
        raise ValueError("Evaluation arrays must be finite numeric 224x160 matrices")
    if probabilities:
        if np.any(mask < 0) or np.any(mask > 1):
            raise ValueError("Prediction probabilities must be within [0, 1]")
        return np.asarray(mask, dtype=np.float32)
    if not np.isin(mask, (0, 1)).all():
        raise ValueError("Ground-truth masks must be binary")
    return np.asarray(mask, dtype=np.uint8)


def _load_approved_holdout(path: Path, *, expected_sha256: str) -> dict[str, Any]:
    if not _valid_sha256(expected_sha256) or _sha256(path) != expected_sha256:
        raise ValueError("Holdout lock checksum does not match approval")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Holdout lock report could not be read") from error
    if (
        not isinstance(payload, dict)
        or set(payload) != set(HOLDOUT_LOCK_FIELDS)
        or payload.get("schema_version") != HOLDOUT_LOCK_SCHEMA
        or payload.get("passed") is not True
    ):
        raise ValueError("Holdout lock report does not match the approved contract")
    if (
        payload.get("split_strategy") != SPLIT_STRATEGY
        or payload.get("split_thresholds") != SPLIT_THRESHOLDS
        or payload.get("holdout_purpose") != HOLDOUT_PURPOSE
        or payload.get("model_selection_access_prohibited") is not True
        or payload.get("threshold_tuning_access_prohibited") is not True
        or payload.get("relabeling_requires_new_dataset_version") is not True
        or not _valid_sha256(payload.get("test_set_commitment_sha256"))
        or not isinstance(payload.get("test_record_count"), int)
        or payload["test_record_count"] <= 0
        or not isinstance(payload.get("test_participant_count"), int)
        or payload["test_participant_count"] <= 0
    ):
        raise ValueError("Holdout lock does not enforce the public evaluation boundary")
    return payload


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{label.title()} must be populated and trimmed")
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label.title()} must be finite")
    return float(value)


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise ValueError("Required segmentation evidence could not be hashed") from error
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a holdout-linked NailSize segmentation evaluation report"
    )
    parser.add_argument("observations", type=Path)
    parser.add_argument("--prediction-mask-root", required=True, type=Path)
    parser.add_argument("--ground-truth-mask-root", required=True, type=Path)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--holdout-lock-report", required=True, type=Path)
    parser.add_argument("--expected-holdout-lock-sha256", required=True)
    parser.add_argument("--prediction-threshold", required=True, type=float)
    parser.add_argument("--threshold-selection-ref", required=True)
    parser.add_argument("--segmentation-review-ref", required=True)
    parser.add_argument("--bootstrap-iterations", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = build_segmentation_evaluation_report(
        load_observations(arguments.observations),
        prediction_mask_root=arguments.prediction_mask_root,
        ground_truth_mask_root=arguments.ground_truth_mask_root,
        dataset_version=arguments.dataset_version,
        model_version=arguments.model_version,
        model_sha256=arguments.model_sha256,
        holdout_lock_path=arguments.holdout_lock_report,
        expected_holdout_lock_sha256=arguments.expected_holdout_lock_sha256,
        prediction_threshold=arguments.prediction_threshold,
        threshold_selection_ref=arguments.threshold_selection_ref,
        segmentation_review_ref=arguments.segmentation_review_ref,
        bootstrap_iterations=arguments.bootstrap_iterations,
        seed=arguments.seed,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
