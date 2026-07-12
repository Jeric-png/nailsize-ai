import hashlib
import json
import sys

import pytest

from nailsize_ml.dataset import DatasetSplit, assign_participant_split
from nailsize_ml.dataset_provenance import COLLECTION_CHANNEL, CONSENT_STATUS
from nailsize_ml.holdout_lock import (
    build_holdout_lock_report,
    main,
    verify_holdout_lock_report,
)

SALT = "test-secret-split-salt"


def participant_for(split: DatasetSplit) -> str:
    for index in range(10_000):
        participant_id = f"participant-{split}-{index}"
        if assign_participant_split(participant_id, salt=SALT) == split:
            return participant_id
    raise AssertionError("Could not find deterministic participant fixture")


def records() -> list[dict[str, str]]:
    return [
        {
            "image_id": f"image-{index}",
            "participant_id": participant_for(split),
            "split": split,
            "image_path": f"images/{index}.png",
            "mask_path": f"masks/{index}.png",
            "dataset_version": "study-1",
            "data_origin": COLLECTION_CHANNEL,
            "consent_status": CONSENT_STATUS,
        }
        for index, split in enumerate(DatasetSplit, 1)
    ]


def write_inputs(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        "".join(json.dumps(record) + "\n" for record in records()), encoding="utf-8"
    )
    salt = tmp_path / "split-salt"
    salt.write_text(SALT, encoding="utf-8")
    return manifest, salt


def write_report(path, manifest, salt) -> str:
    report = build_holdout_lock_report(
        manifest,
        dataset_version="study-1",
        split_salt_path=salt,
        split_salt_id="split-salt-2026-01",
        holdout_lock_review_ref="holdout-review-1",
    )
    path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_builds_and_verifies_private_public_holdout_commitment(tmp_path) -> None:
    manifest, salt = write_inputs(tmp_path)
    report_path = tmp_path / "holdout-lock.json"
    checksum = write_report(report_path, manifest, salt)

    approval = verify_holdout_lock_report(
        report_path,
        manifest,
        split_salt_path=salt,
        expected_lock_sha256=checksum,
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert approval.dataset_version == "study-1"
    assert approval.test_record_count == 1
    assert approval.test_participant_count == 1
    assert len(approval.test_set_commitment_sha256) == 64
    assert report["model_selection_access_prohibited"] is True
    rendered = json.dumps(report)
    assert "participant-test" not in rendered
    assert "image-3" not in rendered
    assert SALT not in rendered


def test_rejects_split_drift_empty_holdout_and_salt_file_whitespace(tmp_path) -> None:
    manifest, salt = write_inputs(tmp_path)
    payloads = records()
    payloads[0]["split"] = DatasetSplit.TEST
    manifest.write_text("".join(json.dumps(record) + "\n" for record in payloads), encoding="utf-8")
    with pytest.raises(ValueError, match="split salt"):
        write_report(tmp_path / "report.json", manifest, salt)

    payloads = [record for record in records() if record["split"] != DatasetSplit.TEST]
    manifest.write_text("".join(json.dumps(record) + "\n" for record in payloads), encoding="utf-8")
    with pytest.raises(ValueError, match="test records"):
        write_report(tmp_path / "report.json", manifest, salt)

    salt.write_text(SALT + "\n", encoding="utf-8")
    manifest.write_text(
        "".join(json.dumps(record) + "\n" for record in records()), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="without whitespace"):
        write_report(tmp_path / "report.json", manifest, salt)


def test_rejects_tampered_lock_manifest_and_approval_checksum(tmp_path) -> None:
    manifest, salt = write_inputs(tmp_path)
    report_path = tmp_path / "holdout-lock.json"
    checksum = write_report(report_path, manifest, salt)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["threshold_tuning_access_prohibited"] = False
    report_path.write_text(json.dumps(report), encoding="utf-8")
    tampered_checksum = hashlib.sha256(report_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="evaluation boundary"):
        verify_holdout_lock_report(
            report_path,
            manifest,
            split_salt_path=salt,
            expected_lock_sha256=tampered_checksum,
        )
    with pytest.raises(ValueError, match="checksum"):
        verify_holdout_lock_report(
            report_path,
            manifest,
            split_salt_path=salt,
            expected_lock_sha256=checksum,
        )

    write_report(report_path, manifest, salt)
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    current_checksum = hashlib.sha256(report_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="manifest checksum"):
        verify_holdout_lock_report(
            report_path,
            manifest,
            split_salt_path=salt,
            expected_lock_sha256=current_checksum,
        )


def test_cli_writes_nested_holdout_lock(tmp_path, monkeypatch) -> None:
    manifest, salt = write_inputs(tmp_path)
    output = tmp_path / "nested" / "holdout-lock.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nailsize-holdout-lock",
            str(manifest),
            "--dataset-version",
            "study-1",
            "--split-salt-file",
            str(salt),
            "--split-salt-id",
            "split-salt-2026-01",
            "--holdout-lock-review-ref",
            "holdout-review-1",
            "--output",
            str(output),
        ],
    )

    main()

    assert json.loads(output.read_text(encoding="utf-8"))["passed"] is True
