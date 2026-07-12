import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dataset import DatasetSplit, assert_no_participant_leakage

SCHEMA_VERSION = "nailsize-research-dataset-provenance@1"
COLLECTION_CHANNEL = "approved_research_study"
CONSENT_STATUS = "active_research_consent"
USAGE_SCOPE = "model_development_only"
MANIFEST_FIELDS = frozenset(
    {
        "image_id",
        "participant_id",
        "split",
        "image_path",
        "mask_path",
        "dataset_version",
        "data_origin",
        "consent_status",
    }
)
REPORT_FIELDS = frozenset(
    {
        "schema_version",
        "dataset_version",
        "collection_channel",
        "consent_status",
        "usage_scope",
        "production_data_excluded",
        "manifest_sha256",
        "record_count",
        "participant_count",
        "split_record_counts",
        "split_participant_counts",
        "research_approval_ref",
        "production_exclusion_review_ref",
        "passed",
    }
)


@dataclass(frozen=True)
class ResearchDatasetApproval:
    dataset_version: str
    provenance_sha256: str
    manifest_sha256: str
    record_count: int
    participant_count: int
    split_record_counts: dict[str, int]
    split_participant_counts: dict[str, int]
    research_approval_ref: str
    production_exclusion_review_ref: str


def build_research_dataset_report(
    manifest_path: str | Path,
    *,
    dataset_version: str,
    research_approval_ref: str,
    production_exclusion_review_ref: str,
) -> dict[str, Any]:
    version = _required_string(dataset_version, "dataset version")
    research_review = _required_string(research_approval_ref, "research approval")
    exclusion_review = _required_string(
        production_exclusion_review_ref, "production exclusion review"
    )
    records = validate_research_manifest(Path(manifest_path), expected_dataset_version=version)
    participants_by_split: dict[DatasetSplit, set[str]] = defaultdict(set)
    records_by_split: dict[DatasetSplit, list[dict[str, str]]] = {
        split: [] for split in DatasetSplit
    }
    for record in records:
        split = DatasetSplit(record["split"])
        participant_id = record["participant_id"]
        participants_by_split[split].add(participant_id)
        records_by_split[split].append({"participant_id": participant_id})
    assert_no_participant_leakage(records_by_split)
    participants = {record["participant_id"] for record in records}
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": version,
        "collection_channel": COLLECTION_CHANNEL,
        "consent_status": CONSENT_STATUS,
        "usage_scope": USAGE_SCOPE,
        "production_data_excluded": True,
        "manifest_sha256": _sha256(Path(manifest_path)),
        "record_count": len(records),
        "participant_count": len(participants),
        "split_record_counts": {
            split.value: len(records_by_split[split]) for split in DatasetSplit
        },
        "split_participant_counts": {
            split.value: len(participants_by_split[split]) for split in DatasetSplit
        },
        "research_approval_ref": research_review,
        "production_exclusion_review_ref": exclusion_review,
        "passed": True,
    }


def verify_research_dataset_report(
    report_path: str | Path,
    manifest_path: str | Path,
    *,
    expected_provenance_sha256: str,
) -> ResearchDatasetApproval:
    report_file = Path(report_path)
    manifest_file = Path(manifest_path)
    if not _valid_sha256(expected_provenance_sha256):
        raise ValueError("Expected dataset provenance SHA-256 must be lowercase hexadecimal")
    if _sha256(report_file) != expected_provenance_sha256:
        raise ValueError("Dataset provenance checksum does not match approval")
    try:
        report = json.loads(report_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Dataset provenance report could not be read") from error
    if not isinstance(report, dict) or set(report) != REPORT_FIELDS:
        raise ValueError("Dataset provenance report fields do not match the contract")
    if report.get("schema_version") != SCHEMA_VERSION or report.get("passed") is not True:
        raise ValueError("Dataset provenance report must use the supported passing schema")
    if (
        report.get("collection_channel") != COLLECTION_CHANNEL
        or report.get("consent_status") != CONSENT_STATUS
        or report.get("usage_scope") != USAGE_SCOPE
        or report.get("production_data_excluded") is not True
    ):
        raise ValueError("Dataset provenance does not enforce the research-only boundary")
    dataset_version = _required_string(report.get("dataset_version"), "dataset version")
    manifest_sha256 = report.get("manifest_sha256")
    if not isinstance(manifest_sha256, str) or not _valid_sha256(manifest_sha256):
        raise ValueError("Dataset manifest SHA-256 is invalid")
    if _sha256(manifest_file) != manifest_sha256:
        raise ValueError("Training manifest checksum does not match dataset provenance")
    records = validate_research_manifest(manifest_file, expected_dataset_version=dataset_version)
    expected = build_research_dataset_report(
        manifest_file,
        dataset_version=dataset_version,
        research_approval_ref=_required_string(
            report.get("research_approval_ref"), "research approval"
        ),
        production_exclusion_review_ref=_required_string(
            report.get("production_exclusion_review_ref"), "production exclusion review"
        ),
    )
    if report != expected or len(records) != expected["record_count"]:
        raise ValueError("Dataset provenance aggregates do not match the approved manifest")
    return ResearchDatasetApproval(
        dataset_version=dataset_version,
        provenance_sha256=expected_provenance_sha256,
        manifest_sha256=manifest_sha256,
        record_count=_positive_integer(report["record_count"], "record count"),
        participant_count=_positive_integer(report["participant_count"], "participant count"),
        split_record_counts=_count_map(report["split_record_counts"], "split record counts"),
        split_participant_counts=_count_map(
            report["split_participant_counts"], "split participant counts"
        ),
        research_approval_ref=report["research_approval_ref"],
        production_exclusion_review_ref=report["production_exclusion_review_ref"],
    )


def validate_research_manifest(
    path: Path, *, expected_dataset_version: str
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    seen_image_ids: set[str] = set()
    try:
        with path.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, 1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid research training manifest record on line {line_number}"
                    ) from error
                if not isinstance(payload, dict) or set(payload) != MANIFEST_FIELDS:
                    raise ValueError(
                        f"Invalid research training manifest record on line {line_number}"
                    )
                record = {key: _required_string(payload.get(key), key) for key in MANIFEST_FIELDS}
                image_id = record["image_id"]
                if image_id in seen_image_ids:
                    raise ValueError(f"Duplicate image ID on line {line_number}")
                if (
                    record["dataset_version"] != expected_dataset_version
                    or record["data_origin"] != COLLECTION_CHANNEL
                    or record["consent_status"] != CONSENT_STATUS
                ):
                    raise ValueError(
                        f"Research boundary violation in manifest record on line {line_number}"
                    )
                try:
                    DatasetSplit(record["split"])
                except ValueError as error:
                    raise ValueError(f"Invalid dataset split on line {line_number}") from error
                seen_image_ids.add(image_id)
                records.append(record)
    except OSError as error:
        raise ValueError("Research training manifest could not be read") from error
    if not records:
        raise ValueError("Research training manifest must contain at least one record")
    return records


def _count_map(value: Any, field: str) -> dict[str, int]:
    expected_keys = {split.value for split in DatasetSplit}
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise ValueError(f"{field.title()} do not match the contract")
    output: dict[str, int] = {}
    for key, count in value.items():
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"{field.title()} must be non-negative integers")
        output[key] = count
    return output


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
        raise ValueError(f"Could not hash required dataset file: {path.name}") from error
    return digest.hexdigest()


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an aggregate research-dataset provenance report"
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--research-approval-ref", required=True)
    parser.add_argument("--production-exclusion-review-ref", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    report = build_research_dataset_report(
        arguments.manifest,
        dataset_version=arguments.dataset_version,
        research_approval_ref=arguments.research_approval_ref,
        production_exclusion_review_ref=arguments.production_exclusion_review_ref,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
