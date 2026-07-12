import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dataset import DEFAULT_THRESHOLDS, DatasetSplit, assign_participant_split
from .dataset_provenance import validate_research_manifest

SCHEMA_VERSION = "nailsize-public-holdout-lock@1"
SPLIT_STRATEGY = "sha256_participant_salt_v1"
HOLDOUT_PURPOSE = "public_release_model_evaluation"
REPORT_FIELDS = frozenset(
    {
        "schema_version",
        "dataset_version",
        "manifest_sha256",
        "split_strategy",
        "split_salt_id",
        "split_thresholds",
        "test_record_count",
        "test_participant_count",
        "test_set_commitment_sha256",
        "holdout_purpose",
        "model_selection_access_prohibited",
        "threshold_tuning_access_prohibited",
        "relabeling_requires_new_dataset_version",
        "holdout_lock_review_ref",
        "passed",
    }
)
SPLIT_THRESHOLDS = {
    "train": DEFAULT_THRESHOLDS.train,
    "validation": DEFAULT_THRESHOLDS.validation,
    "test": 0.15,
}


@dataclass(frozen=True)
class HoldoutLockApproval:
    dataset_version: str
    lock_sha256: str
    manifest_sha256: str
    split_salt_id: str
    test_record_count: int
    test_participant_count: int
    test_set_commitment_sha256: str
    holdout_lock_review_ref: str


def build_holdout_lock_report(
    manifest_path: str | Path,
    *,
    dataset_version: str,
    split_salt_path: str | Path,
    split_salt_id: str,
    holdout_lock_review_ref: str,
) -> dict[str, Any]:
    manifest = Path(manifest_path)
    version = _required_string(dataset_version, "dataset version")
    salt_id = _required_string(split_salt_id, "split salt ID")
    review = _required_string(holdout_lock_review_ref, "holdout lock review")
    salt = _read_split_salt(Path(split_salt_path))
    records = validate_research_manifest(manifest, expected_dataset_version=version)
    _verify_deterministic_splits(records, salt=salt)
    return _build_report(
        records,
        dataset_version=version,
        manifest_sha256=_sha256(manifest),
        split_salt_id=salt_id,
        holdout_lock_review_ref=review,
    )


def verify_holdout_lock_report(
    report_path: str | Path,
    manifest_path: str | Path,
    *,
    split_salt_path: str | Path,
    expected_lock_sha256: str,
) -> HoldoutLockApproval:
    report_file = Path(report_path)
    manifest_file = Path(manifest_path)
    if not _valid_sha256(expected_lock_sha256):
        raise ValueError("Expected holdout lock SHA-256 must be lowercase hexadecimal")
    if _sha256(report_file) != expected_lock_sha256:
        raise ValueError("Holdout lock checksum does not match approval")
    try:
        report = json.loads(report_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Holdout lock report could not be read") from error
    if not isinstance(report, dict) or set(report) != REPORT_FIELDS:
        raise ValueError("Holdout lock report fields do not match the contract")
    if report.get("schema_version") != SCHEMA_VERSION or report.get("passed") is not True:
        raise ValueError("Holdout lock report must use the supported passing schema")
    if (
        report.get("split_strategy") != SPLIT_STRATEGY
        or report.get("split_thresholds") != SPLIT_THRESHOLDS
        or report.get("holdout_purpose") != HOLDOUT_PURPOSE
        or report.get("model_selection_access_prohibited") is not True
        or report.get("threshold_tuning_access_prohibited") is not True
        or report.get("relabeling_requires_new_dataset_version") is not True
    ):
        raise ValueError("Holdout lock does not enforce the public evaluation boundary")
    dataset_version = _required_string(report.get("dataset_version"), "dataset version")
    manifest_sha256 = report.get("manifest_sha256")
    if not _valid_sha256(manifest_sha256) or _sha256(manifest_file) != manifest_sha256:
        raise ValueError("Holdout lock manifest checksum does not match the approved manifest")
    records = validate_research_manifest(manifest_file, expected_dataset_version=dataset_version)
    _verify_deterministic_splits(records, salt=_read_split_salt(Path(split_salt_path)))
    expected = _build_report(
        records,
        dataset_version=dataset_version,
        manifest_sha256=manifest_sha256,
        split_salt_id=_required_string(report.get("split_salt_id"), "split salt ID"),
        holdout_lock_review_ref=_required_string(
            report.get("holdout_lock_review_ref"), "holdout lock review"
        ),
    )
    if report != expected:
        raise ValueError("Holdout lock evidence does not match the approved manifest")
    return HoldoutLockApproval(
        dataset_version=dataset_version,
        lock_sha256=expected_lock_sha256,
        manifest_sha256=manifest_sha256,
        split_salt_id=report["split_salt_id"],
        test_record_count=_positive_integer(report["test_record_count"], "test record count"),
        test_participant_count=_positive_integer(
            report["test_participant_count"], "test participant count"
        ),
        test_set_commitment_sha256=report["test_set_commitment_sha256"],
        holdout_lock_review_ref=report["holdout_lock_review_ref"],
    )


def _build_report(
    records: list[dict[str, str]],
    *,
    dataset_version: str,
    manifest_sha256: str,
    split_salt_id: str,
    holdout_lock_review_ref: str,
) -> dict[str, Any]:
    test_records = [record for record in records if record["split"] == DatasetSplit.TEST]
    if not test_records:
        raise ValueError("Public holdout must contain test records")
    participants = {record["participant_id"] for record in test_records}
    commitment_payload = [
        {"image_id": record["image_id"], "participant_id": record["participant_id"]}
        for record in sorted(
            test_records, key=lambda item: (item["participant_id"], item["image_id"])
        )
    ]
    commitment = hashlib.sha256(
        json.dumps(commitment_payload, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": dataset_version,
        "manifest_sha256": manifest_sha256,
        "split_strategy": SPLIT_STRATEGY,
        "split_salt_id": split_salt_id,
        "split_thresholds": SPLIT_THRESHOLDS,
        "test_record_count": len(test_records),
        "test_participant_count": len(participants),
        "test_set_commitment_sha256": commitment,
        "holdout_purpose": HOLDOUT_PURPOSE,
        "model_selection_access_prohibited": True,
        "threshold_tuning_access_prohibited": True,
        "relabeling_requires_new_dataset_version": True,
        "holdout_lock_review_ref": holdout_lock_review_ref,
        "passed": True,
    }


def _verify_deterministic_splits(records: list[dict[str, str]], *, salt: str) -> None:
    for record in records:
        expected = assign_participant_split(record["participant_id"], salt=salt)
        if record["split"] != expected:
            raise ValueError(
                "Research manifest split does not match the approved participant split salt"
            )


def _read_split_salt(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError("Split salt file could not be read") from error
    if not value or value != value.strip() or "\n" in value or "\r" in value:
        raise ValueError("Split salt file must contain one non-empty value without whitespace")
    return value


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field.title()} must be a populated trimmed string")
    return value


def _positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field.title()} must be a positive integer")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise ValueError(f"Could not hash required holdout file: {path.name}") from error
    return digest.hexdigest()


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lock the participant-disjoint public evaluation holdout"
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--split-salt-file", required=True, type=Path)
    parser.add_argument("--split-salt-id", required=True)
    parser.add_argument("--holdout-lock-review-ref", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    report = build_holdout_lock_report(
        arguments.manifest,
        dataset_version=arguments.dataset_version,
        split_salt_path=arguments.split_salt_file,
        split_salt_id=arguments.split_salt_id,
        holdout_lock_review_ref=arguments.holdout_lock_review_ref,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
