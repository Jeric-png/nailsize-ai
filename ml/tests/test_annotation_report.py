import json
from copy import deepcopy

import numpy as np
import pytest

from nailsize_ml.annotation_report import (
    Adjudication,
    build_annotation_agreement_report,
    load_mask_pairs,
    load_study_bundle,
)


def annotation(
    image_id: str,
    *,
    annotator_id: str,
    width: float = 14.2,
    size: str = "3",
    digit: str = "index",
) -> dict:
    return {
        "schema_version": "1",
        "participant_id": f"participant-{image_id}",
        "image_id": image_id,
        "capture_type": "left_fingers",
        "digit": digit,
        "mask_uri": f"{image_id}.npy",
        "axis": [[0.5, 0.2], [0.5, 0.8]],
        "lateral_boundaries": [[0.3, 0.5], [0.7, 0.5]],
        "physical_width_mm": width,
        "best_fit_size": size,
        "quality_codes": [],
        "annotator_id": annotator_id,
    }


def paired_annotations() -> tuple[list[dict], list[dict]]:
    first = [
        annotation("image-0001", annotator_id="technician-a"),
        annotation("image-0002", annotator_id="technician-a", width=12.0, size="5"),
    ]
    second = [
        annotation("image-0001", annotator_id="technician-b", width=14.3),
        annotation("image-0002", annotator_id="technician-b", width=12.6, size="4"),
    ]
    return first, second


def masks() -> dict:
    return {
        image_id: (np.ones((4, 4), dtype=np.uint8), np.ones((4, 4), dtype=np.uint8))
        for image_id in ("image-0001", "image-0002")
    }


def report(**overrides):
    first, second = paired_annotations()
    arguments = {
        "mask_pairs": masks(),
        "dataset_version": "holdout-1",
        "total_annotated_item_count": 20,
        "agreement_review_ref": "agreement-review-1",
        "adjudication_review_ref": "adjudication-review-1",
        "adjudications": [Adjudication("image-0002", "adjudicator-c", "resolution-2")],
    }
    arguments.update(overrides)
    return build_annotation_agreement_report(first, second, **arguments)


def test_builds_privacy_safe_reviewed_agreement_report() -> None:
    result = report()

    assert result["schema_version"] == "nailsize-annotation-agreement-report@1"
    assert result["passed"] is True
    assert result["dataset_version"] == "holdout-1"
    assert result["paired_item_count"] == 2
    assert result["paired_participant_count"] == 2
    assert result["double_annotation_rate"] == 0.1
    assert result["required_adjudication_count"] == 1
    assert result["completed_adjudication_count"] == 1
    assert result["disagreement_counts"]["best_fit_size"] == 1
    assert result["disagreement_counts"]["physical_width_over_0_5_mm"] == 1
    assert "image-0002" not in json.dumps(result)
    assert "technician-a" not in json.dumps(result)


def test_below_ten_percent_double_annotation_fails_without_hiding_metrics() -> None:
    result = report(total_annotated_item_count=21)

    assert result["passed"] is False
    assert result["dataset_checks"]["minimum_double_annotation_rate"] is False
    assert result["metrics"]["mean_mask_dice"] == 1.0


def test_material_and_declared_boundary_disagreements_require_third_party_adjudication() -> None:
    with pytest.raises(ValueError, match="material annotation disagreement"):
        report(adjudications=[])

    with pytest.raises(ValueError, match="third-party"):
        report(adjudications=[Adjudication("image-0002", "technician-a", "resolution-2")])

    with pytest.raises(ValueError, match="material annotation disagreement"):
        report(disputed_boundary_image_ids=["image-0001"])

    result = report(
        disputed_boundary_image_ids=["image-0001"],
        adjudications=[
            Adjudication("image-0001", "adjudicator-c", "resolution-1"),
            Adjudication("image-0002", "adjudicator-c", "resolution-2"),
        ],
    )
    assert result["disagreement_counts"]["disputed_boundary"] == 1
    assert result["passed"] is True


def test_rejects_identity_drift_and_non_independent_technicians() -> None:
    first, second = paired_annotations()
    second[0]["participant_id"] = "participant-other"
    with pytest.raises(ValueError, match="same participant capture"):
        build_annotation_agreement_report(
            first,
            second,
            mask_pairs=masks(),
            dataset_version="holdout-1",
            total_annotated_item_count=20,
            agreement_review_ref="review-a",
            adjudication_review_ref="review-b",
            adjudications=[Adjudication("image-0002", "adjudicator-c", "resolution")],
        )

    first, second = paired_annotations()
    for item in second:
        item["annotator_id"] = "technician-a"
    with pytest.raises(ValueError, match="two independent"):
        build_annotation_agreement_report(
            first,
            second,
            mask_pairs=masks(),
            dataset_version="holdout-1",
            total_annotated_item_count=20,
            agreement_review_ref="review-a",
            adjudication_review_ref="review-b",
            adjudications=[],
        )


def test_loads_exact_versioned_study_bundle(tmp_path) -> None:
    first, second = paired_annotations()
    payload = {
        "schema_version": "nailsize-annotation-study@1",
        "dataset_version": "holdout-1",
        "total_annotated_item_count": 20,
        "agreement_review_ref": "agreement-review-1",
        "adjudication_review_ref": "adjudication-review-1",
        "first_annotations": first,
        "second_annotations": second,
        "adjudications": [
            {
                "image_id": "image-0002",
                "adjudicator_id": "adjudicator-c",
                "resolution_ref": "resolution-2",
            }
        ],
        "disputed_boundary_image_ids": [],
    }
    path = tmp_path / "study.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_study_bundle(path)

    assert loaded[0] == first
    assert loaded[1] == second
    assert loaded[2:6] == (
        "holdout-1",
        20,
        "agreement-review-1",
        "adjudication-review-1",
    )
    assert loaded[6] == [Adjudication("image-0002", "adjudicator-c", "resolution-2")]

    payload["unexpected"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="fields do not match"):
        load_study_bundle(path)

    del payload["unexpected"]
    payload["agreement_review_ref"] = 123
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty strings"):
        load_study_bundle(path)


def test_loads_bounded_non_pickled_masks_from_separate_roots(tmp_path) -> None:
    first, second = paired_annotations()
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    for item in first:
        np.save(first_root / item["mask_uri"], np.ones((3, 4), dtype=np.uint8))
    for item in second:
        np.save(second_root / item["mask_uri"], np.ones((3, 4), dtype=np.uint8))

    loaded = load_mask_pairs(first, second, first_root=first_root, second_root=second_root)

    assert set(loaded) == {"image-0001", "image-0002"}
    assert loaded["image-0001"][0].shape == (3, 4)

    escaped = deepcopy(first)
    escaped[0]["mask_uri"] = "../outside.npy"
    with pytest.raises(ValueError, match="safe relative"):
        load_mask_pairs(escaped, second, first_root=first_root, second_root=second_root)
