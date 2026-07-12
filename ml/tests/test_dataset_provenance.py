import hashlib
import json
import sys
from copy import deepcopy

import pytest

from nailsize_ml.dataset_provenance import (
    COLLECTION_CHANNEL,
    CONSENT_STATUS,
    build_research_dataset_report,
    main,
    verify_research_dataset_report,
)


def records() -> list[dict[str, str]]:
    return [
        {
            "image_id": f"image-{index:03d}",
            "participant_id": f"participant-{index:03d}",
            "split": split,
            "image_path": f"images/{index}.png",
            "mask_path": f"masks/{index}.png",
            "dataset_version": "study-1",
            "data_origin": COLLECTION_CHANNEL,
            "consent_status": CONSENT_STATUS,
        }
        for index, split in enumerate(("train", "validation", "test"), 1)
    ]


def write_manifest(path, payloads=None) -> None:
    path.write_text(
        "".join(json.dumps(item) + "\n" for item in (payloads or records())),
        encoding="utf-8",
    )


def write_report(path, manifest) -> str:
    report = build_research_dataset_report(
        manifest,
        dataset_version="study-1",
        research_approval_ref="research-review-1",
        production_exclusion_review_ref="privacy-review-1",
    )
    path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_builds_and_verifies_aggregate_only_research_provenance(tmp_path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    report_path = tmp_path / "provenance.json"
    write_manifest(manifest)
    checksum = write_report(report_path, manifest)

    approval = verify_research_dataset_report(
        report_path, manifest, expected_provenance_sha256=checksum
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert approval.dataset_version == "study-1"
    assert approval.record_count == 3
    assert approval.participant_count == 3
    assert approval.split_record_counts == {"train": 1, "validation": 1, "test": 1}
    assert report["production_data_excluded"] is True
    rendered = json.dumps(report)
    for private_value in ("image-001", "participant-001", "images/1.png"):
        assert private_value not in rendered


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("data_origin", "production_upload", "boundary violation"),
        ("consent_status", "withdrawn", "boundary violation"),
        ("dataset_version", "other", "boundary violation"),
        ("unexpected", "value", "Invalid research"),
    ],
)
def test_rejects_nonresearch_or_unapproved_manifest_records(
    tmp_path, field: str, value: str, message: str
) -> None:
    manifest = tmp_path / "manifest.jsonl"
    payloads = records()
    payloads[0][field] = value
    write_manifest(manifest, payloads)

    with pytest.raises(ValueError, match=message):
        build_research_dataset_report(
            manifest,
            dataset_version="study-1",
            research_approval_ref="research-review-1",
            production_exclusion_review_ref="privacy-review-1",
        )


def test_rejects_participant_split_leakage_and_report_tampering(tmp_path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    payloads = records()
    payloads[1]["participant_id"] = payloads[0]["participant_id"]
    write_manifest(manifest, payloads)
    with pytest.raises(ValueError, match="appears in"):
        build_research_dataset_report(
            manifest,
            dataset_version="study-1",
            research_approval_ref="research-review-1",
            production_exclusion_review_ref="privacy-review-1",
        )

    write_manifest(manifest)
    report_path = tmp_path / "provenance.json"
    checksum = write_report(report_path, manifest)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    tampered = deepcopy(report)
    tampered["record_count"] = 4
    report_path.write_text(json.dumps(tampered), encoding="utf-8")
    tampered_checksum = hashlib.sha256(report_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="aggregates"):
        verify_research_dataset_report(
            report_path, manifest, expected_provenance_sha256=tampered_checksum
        )
    with pytest.raises(ValueError, match="checksum"):
        verify_research_dataset_report(report_path, manifest, expected_provenance_sha256=checksum)


def test_rejects_non_string_expected_provenance_checksum(tmp_path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    report_path = tmp_path / "provenance.json"
    write_manifest(manifest)
    write_report(report_path, manifest)

    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        verify_research_dataset_report(
            report_path,
            manifest,
            expected_provenance_sha256=None,  # type: ignore[arg-type]
        )


def test_cli_writes_nested_report(tmp_path, monkeypatch) -> None:
    manifest = tmp_path / "manifest.jsonl"
    output = tmp_path / "nested" / "provenance.json"
    write_manifest(manifest)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nailsize-dataset-provenance-report",
            str(manifest),
            "--dataset-version",
            "study-1",
            "--research-approval-ref",
            "research-review-1",
            "--production-exclusion-review-ref",
            "privacy-review-1",
            "--output",
            str(output),
        ],
    )

    main()

    assert json.loads(output.read_text(encoding="utf-8"))["passed"] is True
