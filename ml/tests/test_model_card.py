from copy import deepcopy

import pytest

from nailsize_ml.model_card import render_model_card


@pytest.fixture
def metadata() -> dict:
    return {
        "model_name": "NailSize segmentation",
        "model_version": "release-1",
        "model_sha256": "a" * 64,
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


@pytest.fixture
def report() -> dict:
    metric_values = {
        "nail_count": 2000,
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
            "metrics": metric_values,
            "confidence_intervals_95": {
                name: {"lower": value * 0.9, "upper": value * 1.1}
                for name, value in metric_values.items()
                if name != "nail_count"
            },
            "passed": True,
        },
        "adequately_sampled_cohorts": [
            {
                "dimension": dimension,
                "value": value,
                "participant_count": 50,
                "nail_count": 500,
                "metrics": {"width_mae_mm": 0.45, "exact_size_rate": 0.91},
                "passed": True,
            }
            for dimension, value in (
                ("skin_tone", "monk-5"),
                ("curvature", "medium"),
                ("width", "medium"),
                ("device", "phone-a"),
            )
        ],
    }


def test_renders_required_evidence_and_limitations(metadata: dict, report: dict) -> None:
    card = render_model_card(metadata, report)

    assert "# NailSize segmentation Model Card" in card
    assert "`release-1`" in card
    assert "200 participants / 2000 nails" in card
    assert "Participant-clustered 95% CI" in card
    assert "skin_tone | monk-5" in card
    assert "Measures projected width" in card
    assert "Privacy Security: Privacy review P-1" in card


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("model_sha256", "bad", "SHA-256"),
        ("limitations", [], "limitations"),
        ("onnx_parity_max_abs_error", 0.001, "parity"),
    ],
)
def test_rejects_incomplete_or_unapproved_metadata(
    metadata: dict, report: dict, field: str, value: object, message: str
) -> None:
    metadata[field] = value
    with pytest.raises(ValueError, match=message):
        render_model_card(metadata, report)


def test_rejects_failed_accuracy_or_missing_approval(metadata: dict, report: dict) -> None:
    failed = deepcopy(report)
    failed["passed"] = False
    with pytest.raises(ValueError, match="must pass"):
        render_model_card(metadata, failed)

    del metadata["approvals"]["nail_tech"]
    with pytest.raises(ValueError, match="nail_tech"):
        render_model_card(metadata, report)
