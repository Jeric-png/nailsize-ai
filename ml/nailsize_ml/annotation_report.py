import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .annotation_quality import agreement_report, validate_annotation

MINIMUM_DOUBLE_ANNOTATION_RATE = 0.10
MAX_MASK_PIXELS = 25_000_000
MAX_MASK_FILE_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class Adjudication:
    image_id: str
    adjudicator_id: str
    resolution_ref: str


def build_annotation_agreement_report(
    first: Sequence[Mapping[str, Any]],
    second: Sequence[Mapping[str, Any]],
    *,
    mask_pairs: Mapping[str, tuple[NDArray[np.uint8], NDArray[np.uint8]]],
    dataset_version: str,
    total_annotated_item_count: int,
    agreement_review_ref: str,
    adjudication_review_ref: str,
    adjudications: Sequence[Adjudication],
    disputed_boundary_image_ids: Sequence[str] = (),
) -> dict[str, Any]:
    left, right, technician_ids = _validate_annotation_pairs(first, second)
    if not dataset_version.strip():
        raise ValueError("Dataset version is required")
    if (
        isinstance(total_annotated_item_count, bool)
        or not isinstance(total_annotated_item_count, int)
        or total_annotated_item_count < len(left)
    ):
        raise ValueError("Total annotated item count must include every paired item")
    if not agreement_review_ref.strip() or not adjudication_review_ref.strip():
        raise ValueError("Agreement and adjudication review references are required")

    paired_ids = {str(item["image_id"]) for item in left}
    disputed_ids = set(disputed_boundary_image_ids)
    if len(disputed_ids) != len(disputed_boundary_image_ids) or not disputed_ids <= paired_ids:
        raise ValueError("Disputed boundary IDs must be unique paired image IDs")

    right_by_id = {str(item["image_id"]): item for item in right}
    disagreement_ids: dict[str, set[str]] = {
        "digit": set(),
        "quality_codes": set(),
        "best_fit_size": set(),
        "physical_width_over_0_5_mm": set(),
        "disputed_boundary": disputed_ids,
    }
    for left_item in left:
        image_id = str(left_item["image_id"])
        right_item = right_by_id[image_id]
        if left_item["digit"] != right_item["digit"]:
            disagreement_ids["digit"].add(image_id)
        if set(left_item["quality_codes"]) != set(right_item["quality_codes"]):
            disagreement_ids["quality_codes"].add(image_id)
        if str(left_item["best_fit_size"]) != str(right_item["best_fit_size"]):
            disagreement_ids["best_fit_size"].add(image_id)
        if (
            abs(float(left_item["physical_width_mm"]) - float(right_item["physical_width_mm"]))
            > 0.5
        ):
            disagreement_ids["physical_width_over_0_5_mm"].add(image_id)

    required_adjudications = set().union(*disagreement_ids.values())
    adjudication_by_id = _validate_adjudications(
        adjudications,
        paired_ids=paired_ids,
        technician_ids=technician_ids,
    )
    missing_adjudications = required_adjudications - adjudication_by_id.keys()
    if missing_adjudications:
        raise ValueError("Every material annotation disagreement requires adjudication")

    metrics = agreement_report(left, right, mask_pairs=mask_pairs)
    double_annotation_rate = len(left) / total_annotated_item_count
    dataset_checks = {
        "minimum_double_annotation_rate": (
            double_annotation_rate >= MINIMUM_DOUBLE_ANNOTATION_RATE
        ),
        "two_independent_technicians": len(technician_ids) == 2,
        "agreement_review_present": bool(agreement_review_ref.strip()),
        "adjudication_review_present": bool(adjudication_review_ref.strip()),
        "material_disagreements_adjudicated": not missing_adjudications,
    }
    return {
        "schema_version": "nailsize-annotation-agreement-report@1",
        "dataset_version": dataset_version,
        "total_annotated_item_count": total_annotated_item_count,
        "paired_item_count": len(left),
        "paired_participant_count": len({str(item["participant_id"]) for item in left}),
        "double_annotation_rate": double_annotation_rate,
        "metrics": asdict(metrics),
        "disagreement_counts": {
            name: len(image_ids) for name, image_ids in disagreement_ids.items()
        },
        "required_adjudication_count": len(required_adjudications),
        "completed_adjudication_count": len(adjudication_by_id),
        "dataset_checks": dataset_checks,
        "agreement_review_ref": agreement_review_ref,
        "adjudication_review_ref": adjudication_review_ref,
        "passed": all(dataset_checks.values()),
    }


def load_study_bundle(
    path: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    str,
    int,
    str,
    str,
    list[Adjudication],
    list[str],
]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Annotation study bundle must be valid JSON") from error
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != "nailsize-annotation-study@1"
    ):
        raise ValueError("Unsupported annotation study bundle schema")
    expected_fields = {
        "schema_version",
        "dataset_version",
        "total_annotated_item_count",
        "agreement_review_ref",
        "adjudication_review_ref",
        "first_annotations",
        "second_annotations",
        "adjudications",
        "disputed_boundary_image_ids",
    }
    if set(payload) != expected_fields:
        raise ValueError("Annotation study bundle fields do not match the contract")
    try:
        first = [dict(item) for item in payload["first_annotations"]]
        second = [dict(item) for item in payload["second_annotations"]]
        adjudications = [Adjudication(**item) for item in payload["adjudications"]]
        disputed = list(payload["disputed_boundary_image_ids"])
    except (KeyError, TypeError) as error:
        raise ValueError("Annotation study bundle records are malformed") from error
    for field in ("dataset_version", "agreement_review_ref", "adjudication_review_ref"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError("Annotation study bundle references must be non-empty strings")
    if any(not isinstance(item, str) or not item.strip() for item in disputed):
        raise ValueError("Disputed boundary IDs must be non-empty strings")
    return (
        first,
        second,
        payload["dataset_version"],
        payload["total_annotated_item_count"],
        payload["agreement_review_ref"],
        payload["adjudication_review_ref"],
        adjudications,
        disputed,
    )


def load_mask_pairs(
    first: Sequence[Mapping[str, Any]],
    second: Sequence[Mapping[str, Any]],
    *,
    first_root: Path,
    second_root: Path,
) -> dict[str, tuple[NDArray[np.uint8], NDArray[np.uint8]]]:
    left, right, _ = _validate_annotation_pairs(first, second)
    right_by_id = {str(item["image_id"]): item for item in right}
    return {
        str(item["image_id"]): (
            _load_mask(first_root, str(item["mask_uri"])),
            _load_mask(second_root, str(right_by_id[str(item["image_id"])]["mask_uri"])),
        )
        for item in left
    }


def _load_mask(root: Path, relative_uri: str) -> NDArray[np.uint8]:
    relative = Path(relative_uri)
    if relative.is_absolute() or relative.suffix.lower() != ".npy" or ".." in relative.parts:
        raise ValueError("Mask URIs must be safe relative .npy paths")
    root = root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError("Mask URI escapes its approved root") from error
    if not path.is_file() or path.stat().st_size > MAX_MASK_FILE_BYTES:
        raise ValueError("Mask file is missing or exceeds the size limit")
    try:
        mask = np.load(path, allow_pickle=False, mmap_mode="r")
    except (OSError, ValueError) as error:
        raise ValueError("Mask file is not a valid non-pickled NumPy array") from error
    if mask.ndim != 2 or mask.size == 0 or mask.size > MAX_MASK_PIXELS:
        raise ValueError("Masks must be non-empty two-dimensional arrays within the pixel limit")
    if mask.dtype.kind not in "biuf":
        raise ValueError("Masks must use a numeric or boolean dtype")
    return np.asarray(mask > 0, dtype=np.uint8)


def _validate_annotation_pairs(
    first: Sequence[Mapping[str, Any]], second: Sequence[Mapping[str, Any]]
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], frozenset[str]]:
    left = list(first)
    right = list(second)
    if len(left) != len(right) or not left:
        raise ValueError("Paired non-empty annotations are required")
    for item in (*left, *right):
        if validate_annotation(item):
            raise ValueError("Annotation failed the quality contract")
        required = {"lateral_boundaries", "quality_codes", "annotator_id"}
        if not required <= item.keys():
            raise ValueError("Annotation is missing agreement fields")
        if not isinstance(item["quality_codes"], list) or any(
            not isinstance(code, str) or not code.strip() for code in item["quality_codes"]
        ):
            raise ValueError("Annotation quality codes must be non-empty strings")
        if len(set(item["quality_codes"])) != len(item["quality_codes"]):
            raise ValueError("Annotation quality codes must be unique")
        if not isinstance(item["annotator_id"], str) or not item["annotator_id"].strip():
            raise ValueError("Annotation technician identity is required")
    left_by_id = {str(item["image_id"]): item for item in left}
    right_by_id = {str(item["image_id"]): item for item in right}
    if (
        len(left_by_id) != len(left)
        or len(right_by_id) != len(right)
        or left_by_id.keys() != right_by_id.keys()
    ):
        raise ValueError("Annotation image IDs must be unique and paired")
    for image_id, left_item in left_by_id.items():
        right_item = right_by_id[image_id]
        if (
            left_item["participant_id"] != right_item["participant_id"]
            or left_item["capture_type"] != right_item["capture_type"]
        ):
            raise ValueError("Paired annotations must describe the same participant capture")
    left_technicians = {str(item["annotator_id"]) for item in left}
    right_technicians = {str(item["annotator_id"]) for item in right}
    if (
        len(left_technicians) != 1
        or len(right_technicians) != 1
        or left_technicians == right_technicians
    ):
        raise ValueError("Exactly two independent technicians must annotate every pair")
    return left, right, frozenset(left_technicians | right_technicians)


def _validate_adjudications(
    adjudications: Sequence[Adjudication],
    *,
    paired_ids: set[str],
    technician_ids: frozenset[str],
) -> dict[str, Adjudication]:
    records = list(adjudications)
    by_id = {item.image_id: item for item in records}
    if len(by_id) != len(records) or not by_id.keys() <= paired_ids:
        raise ValueError("Adjudications must use unique paired image IDs")
    for item in records:
        if (
            not item.adjudicator_id.strip()
            or item.adjudicator_id in technician_ids
            or not item.resolution_ref.strip()
        ):
            raise ValueError("Adjudication requires a third-party adjudicator and resolution")
    return by_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a reviewed annotation agreement report")
    parser.add_argument("study_bundle", type=Path)
    parser.add_argument("--first-mask-root", type=Path, required=True)
    parser.add_argument("--second-mask-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    (
        first,
        second,
        dataset_version,
        total,
        agreement_review,
        adjudication_review,
        adjudications,
        disputed,
    ) = load_study_bundle(arguments.study_bundle)
    report = build_annotation_agreement_report(
        first,
        second,
        mask_pairs=load_mask_pairs(
            first,
            second,
            first_root=arguments.first_mask_root,
            second_root=arguments.second_mask_root,
        ),
        dataset_version=dataset_version,
        total_annotated_item_count=total,
        agreement_review_ref=agreement_review,
        adjudication_review_ref=adjudication_review,
        adjudications=adjudications,
        disputed_boundary_image_ids=disputed,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
