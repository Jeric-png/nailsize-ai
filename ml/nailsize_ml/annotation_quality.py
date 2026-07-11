from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

CAPTURE_TYPES = {"left_fingers", "left_thumb", "right_fingers", "right_thumb"}
DIGITS = {"thumb", "index", "middle", "ring", "pinky"}


@dataclass(frozen=True)
class AgreementReport:
    item_count: int
    mean_mask_dice: float
    mean_boundary_distance_normalized: float
    digit_agreement: float
    quality_code_agreement: float
    best_fit_agreement: float
    best_fit_kappa: float
    mean_width_difference_mm: float


def validate_annotation(record: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    required = {
        "schema_version",
        "participant_id",
        "image_id",
        "capture_type",
        "digit",
        "mask_uri",
        "axis",
        "physical_width_mm",
        "best_fit_size",
    }
    for field in sorted(required - record.keys()):
        errors.append(f"missing:{field}")
    if record.get("capture_type") not in CAPTURE_TYPES:
        errors.append("invalid:capture_type")
    if record.get("digit") not in DIGITS:
        errors.append("invalid:digit")
    width = record.get("physical_width_mm")
    if not isinstance(width, (int, float)) or width <= 0:
        errors.append("invalid:physical_width_mm")
    if str(record.get("best_fit_size")) not in {str(value) for value in range(10)}:
        errors.append("invalid:best_fit_size")
    axis = record.get("axis")
    if not _valid_normalized_line(axis):
        errors.append("invalid:axis")
    return tuple(errors)


def _valid_normalized_line(value: Any) -> bool:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 2:
        return False
    return all(
        isinstance(point, Sequence)
        and len(point) == 2
        and all(
            isinstance(coordinate, (int, float)) and 0 <= coordinate <= 1 for coordinate in point
        )
        for point in value
    )


def mask_dice(first: NDArray[np.uint8], second: NDArray[np.uint8]) -> float:
    if first.shape != second.shape:
        raise ValueError("Masks must have identical shapes")
    first_binary = first > 0
    second_binary = second > 0
    denominator = int(first_binary.sum() + second_binary.sum())
    if denominator == 0:
        return 1.0
    intersection = int(np.logical_and(first_binary, second_binary).sum())
    return 2 * intersection / denominator


def symmetric_boundary_distance(
    first: Sequence[Sequence[float]], second: Sequence[Sequence[float]]
) -> float:
    first_points = np.asarray(first, dtype=float)
    second_points = np.asarray(second, dtype=float)
    if (
        first_points.ndim != 2
        or second_points.ndim != 2
        or first_points.shape[1:] != (2,)
        or second_points.shape[1:] != (2,)
        or len(first_points) == 0
        or len(second_points) == 0
    ):
        raise ValueError("Boundary points must be non-empty two-dimensional coordinates")
    distances = np.linalg.norm(first_points[:, None, :] - second_points[None, :, :], axis=2)
    return float((distances.min(axis=1).mean() + distances.min(axis=0).mean()) / 2)


def _cohens_kappa(first: Sequence[str], second: Sequence[str]) -> float:
    if len(first) != len(second) or not first:
        raise ValueError("Paired non-empty labels are required")
    observed = sum(left == right for left, right in zip(first, second, strict=True)) / len(first)
    first_counts = Counter(first)
    second_counts = Counter(second)
    labels = set(first_counts) | set(second_counts)
    expected = sum(
        (first_counts[label] / len(first)) * (second_counts[label] / len(second))
        for label in labels
    )
    return 1.0 if expected == 1.0 and observed == 1.0 else (observed - expected) / (1 - expected)


def agreement_report(
    first: Sequence[Mapping[str, Any]],
    second: Sequence[Mapping[str, Any]],
    *,
    mask_pairs: Mapping[str, tuple[NDArray[np.uint8], NDArray[np.uint8]]],
) -> AgreementReport:
    if len(first) != len(second) or not first:
        raise ValueError("Paired non-empty annotations are required")
    first_by_id = {str(item["image_id"]): item for item in first}
    second_by_id = {str(item["image_id"]): item for item in second}
    if first_by_id.keys() != second_by_id.keys() or len(first_by_id) != len(first):
        raise ValueError("Annotation image IDs must be unique and paired")
    ordered_ids = sorted(first_by_id)
    if set(mask_pairs) != set(ordered_ids):
        raise ValueError("Mask pairs must exist for every paired annotation")
    left = [first_by_id[item_id] for item_id in ordered_ids]
    right = [second_by_id[item_id] for item_id in ordered_ids]
    mean_dice = sum(mask_dice(*mask_pairs[item_id]) for item_id in ordered_ids) / len(left)
    mean_boundary_distance = sum(
        symmetric_boundary_distance(a["lateral_boundaries"], b["lateral_boundaries"])
        for a, b in zip(left, right, strict=True)
    ) / len(left)
    digit_agreement = sum(a["digit"] == b["digit"] for a, b in zip(left, right, strict=True)) / len(
        left
    )
    quality_agreement = sum(
        set(a.get("quality_codes", ())) == set(b.get("quality_codes", ()))
        for a, b in zip(left, right, strict=True)
    ) / len(left)
    left_fit = [str(item["best_fit_size"]) for item in left]
    right_fit = [str(item["best_fit_size"]) for item in right]
    fit_agreement = sum(a == b for a, b in zip(left_fit, right_fit, strict=True)) / len(left)
    mean_width_difference = sum(
        abs(float(a["physical_width_mm"]) - float(b["physical_width_mm"]))
        for a, b in zip(left, right, strict=True)
    ) / len(left)
    return AgreementReport(
        item_count=len(left),
        mean_mask_dice=mean_dice,
        mean_boundary_distance_normalized=mean_boundary_distance,
        digit_agreement=digit_agreement,
        quality_code_agreement=quality_agreement,
        best_fit_agreement=fit_agreement,
        best_fit_kappa=_cohens_kappa(left_fit, right_fit),
        mean_width_difference_mm=mean_width_difference,
    )
