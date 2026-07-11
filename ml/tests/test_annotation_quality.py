import json
from pathlib import Path

import numpy as np
import pytest
from jsonschema import Draft202012Validator

from nailsize_ml.annotation_quality import (
    agreement_report,
    mask_dice,
    symmetric_boundary_distance,
    validate_annotation,
)


def annotation(image_id: str, *, width: float = 14.2, size: str = "3", digit: str = "index"):
    return {
        "schema_version": "1",
        "participant_id": "participant-001",
        "image_id": image_id,
        "capture_type": "left_fingers",
        "digit": digit,
        "mask_uri": f"masks/{image_id}.png",
        "axis": [[0.5, 0.2], [0.5, 0.8]],
        "lateral_boundaries": [[0.3, 0.5], [0.7, 0.5]],
        "physical_width_mm": width,
        "best_fit_size": size,
        "quality_codes": [],
        "annotator_id": "annotator-a",
    }


def test_validates_required_fields_and_normalized_geometry() -> None:
    assert validate_annotation(annotation("image-001")) == ()
    invalid = annotation("image-002")
    invalid["axis"] = [[-0.1, 0.2], [0.5, 1.1]]
    invalid["physical_width_mm"] = -2
    errors = validate_annotation(invalid)
    assert "invalid:axis" in errors
    assert "invalid:physical_width_mm" in errors


def test_versioned_json_schema_accepts_complete_annotation() -> None:
    schema_path = Path(__file__).parents[1] / "annotations" / "nail-annotation.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(annotation("image-001")))
    assert errors == []


def test_mask_dice_handles_overlap_and_empty_masks() -> None:
    first = np.zeros((20, 20), dtype=np.uint8)
    second = np.zeros_like(first)
    assert mask_dice(first, second) == 1.0
    first[2:12, 2:12] = 1
    second[4:14, 2:12] = 1
    assert mask_dice(first, second) == pytest.approx(0.8)


def test_symmetric_boundary_distance_is_order_independent() -> None:
    first = [[0.2, 0.5], [0.8, 0.5]]
    second = [[0.25, 0.5], [0.75, 0.5]]
    assert symmetric_boundary_distance(first, second) == pytest.approx(0.05)
    assert symmetric_boundary_distance(second, first) == pytest.approx(0.05)


def test_reports_paired_technician_agreement() -> None:
    first = [annotation("image-1", size="3"), annotation("image-2", width=12.0, size="5")]
    second = [
        annotation("image-1", width=14.4, size="3"),
        annotation("image-2", width=12.4, size="4"),
    ]
    first[0]["quality_codes"] = ["blur"]
    second[0]["quality_codes"] = ["blur"]
    masks = {
        image_id: (
            np.ones((4, 4), dtype=np.uint8),
            np.ones((4, 4), dtype=np.uint8),
        )
        for image_id in ("image-1", "image-2")
    }
    report = agreement_report(first, second, mask_pairs=masks)
    assert report.item_count == 2
    assert report.mean_mask_dice == 1.0
    assert report.mean_boundary_distance_normalized == 0.0
    assert report.digit_agreement == 1.0
    assert report.quality_code_agreement == 1.0
    assert report.best_fit_agreement == 0.5
    assert report.mean_width_difference_mm == pytest.approx(0.3)


def test_rejects_unpaired_annotations() -> None:
    with pytest.raises(ValueError, match="paired"):
        agreement_report(
            [annotation("image-1")],
            [annotation("image-2")],
            mask_pairs={"image-1": (np.zeros((1, 1)), np.zeros((1, 1)))},
        )
