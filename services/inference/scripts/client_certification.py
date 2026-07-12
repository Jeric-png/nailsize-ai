"""Build aggregate browser-matrix and accessibility certification evidence."""

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

STUDY_SCHEMA_VERSION = "nailsize-client-certification-study@1"
REPORT_SCHEMA_VERSION = "nailsize-client-certification@1"
PLATFORMS = (
    "ios_safari",
    "android_chrome",
    "desktop_chrome",
    "desktop_edge",
    "desktop_firefox",
    "desktop_safari",
)
VERSION_SLOTS = ("current", "previous_1", "previous_2")
MOBILE_PLATFORMS = frozenset({"ios_safari", "android_chrome"})
EXECUTION_ENVIRONMENTS = frozenset({"physical_device", "hosted_real_browser"})
_RELEASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_EVIDENCE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,511}$")


@dataclass(frozen=True)
class BrowserCertification:
    platform: str
    version_slot: str
    browser_major: int
    execution_environment: str
    run_ref: str
    passed: bool


@dataclass(frozen=True)
class AccessibilityCertification:
    automated_mobile_scan_ref: str
    automated_mobile_passed: bool
    automated_desktop_scan_ref: str
    automated_desktop_passed: bool
    keyboard_review_ref: str
    keyboard_passed: bool
    voiceover_review_ref: str
    voiceover_passed: bool
    talkback_review_ref: str
    talkback_passed: bool
    blocking_issue_count: int
    accessibility_review_ref: str


def build_client_certification_report(
    *,
    release_version: str,
    tested_commit_sha: str,
    browser_matrix: list[BrowserCertification],
    accessibility: AccessibilityCertification,
    browser_version_review_ref: str,
    client_certification_review_ref: str,
) -> dict[str, Any]:
    if _RELEASE_ID.fullmatch(release_version) is None:
        raise ValueError("Release version must be a bounded immutable identifier")
    if _COMMIT_SHA.fullmatch(tested_commit_sha) is None:
        raise ValueError("Tested commit must be an exact lowercase 40-character SHA")
    if not _optional_ref(browser_version_review_ref) or not _optional_ref(
        client_certification_review_ref
    ):
        raise ValueError("Certification review references must use bounded safe identifiers")

    records = list(browser_matrix)
    by_key: dict[tuple[str, str], BrowserCertification] = {}
    for item in records:
        _validate_browser_record(item)
        key = (item.platform, item.version_slot)
        if key in by_key:
            raise ValueError("Browser matrix entries must be unique by platform and version slot")
        by_key[key] = item

    expected_keys = {(platform, slot) for platform in PLATFORMS for slot in VERSION_SLOTS}
    missing_keys = sorted(expected_keys - set(by_key))
    version_coverage = {
        platform: _has_consecutive_versions(platform, by_key) for platform in PLATFORMS
    }
    browser_refs_complete = _review_ref(browser_version_review_ref) and all(
        _review_ref(item.run_ref) for item in records
    )
    browser_evidence_complete = (
        not missing_keys
        and set(by_key) == expected_keys
        and all(version_coverage.values())
        and browser_refs_complete
    )
    browser_passed = browser_evidence_complete and all(item.passed for item in records)

    accessibility_dict = asdict(accessibility)
    _validate_accessibility(accessibility)
    accessibility_refs = [
        value for key, value in accessibility_dict.items() if key.endswith("_ref")
    ]
    accessibility_evidence_complete = all(_review_ref(value) for value in accessibility_refs)
    accessibility_checks = {
        "automated_mobile": accessibility.automated_mobile_passed,
        "automated_desktop": accessibility.automated_desktop_passed,
        "keyboard": accessibility.keyboard_passed,
        "voiceover": accessibility.voiceover_passed,
        "talkback": accessibility.talkback_passed,
        "zero_blocking_issues": accessibility.blocking_issue_count == 0,
    }
    accessibility_passed = accessibility_evidence_complete and all(accessibility_checks.values())
    certification_review_present = _review_ref(client_certification_review_ref)
    evidence_complete = (
        browser_evidence_complete
        and accessibility_evidence_complete
        and certification_review_present
    )
    passed = evidence_complete and browser_passed and accessibility_passed
    if passed:
        decision = "client_validation_passed"
    elif not evidence_complete:
        decision = "insufficient_evidence"
    else:
        decision = "client_validation_failed"

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "release_version": release_version,
        "tested_commit_sha": tested_commit_sha,
        "required_platforms": list(PLATFORMS),
        "required_version_slots": list(VERSION_SLOTS),
        "browser_version_review_ref": browser_version_review_ref,
        "client_certification_review_ref": client_certification_review_ref,
        "certification_review_present": certification_review_present,
        "browser_matrix": [asdict(by_key[key]) for key in sorted(by_key)],
        "missing_browser_requirements": [
            {"platform": platform, "version_slot": slot} for platform, slot in missing_keys
        ],
        "consecutive_version_coverage": version_coverage,
        "browser_evidence_complete": browser_evidence_complete,
        "browser_passed": browser_passed,
        "accessibility": {
            **accessibility_dict,
            "checks": accessibility_checks,
            "evidence_complete": accessibility_evidence_complete,
            "passed": accessibility_passed,
        },
        "decision": decision,
        "public_launch_may_continue": passed,
        "passed": passed,
    }


def _validate_browser_record(item: BrowserCertification) -> None:
    if item.platform not in PLATFORMS or item.version_slot not in VERSION_SLOTS:
        raise ValueError("Browser records require an approved platform and version slot")
    if isinstance(item.browser_major, bool) or not isinstance(item.browser_major, int):
        raise ValueError("Browser major versions must be positive integers")
    if item.browser_major <= 0:
        raise ValueError("Browser major versions must be positive integers")
    if item.execution_environment not in EXECUTION_ENVIRONMENTS:
        raise ValueError("Browser execution must use a physical device or hosted real browser")
    if item.platform in MOBILE_PLATFORMS and item.execution_environment != "physical_device":
        raise ValueError("Mobile browser certification requires a physical device")
    if not _optional_ref(item.run_ref):
        raise ValueError("Browser run references must use bounded safe identifiers")
    if not isinstance(item.passed, bool):
        raise ValueError("Browser pass results must be booleans")


def _has_consecutive_versions(
    platform: str, records: dict[tuple[str, str], BrowserCertification]
) -> bool:
    items = [records.get((platform, slot)) for slot in VERSION_SLOTS]
    if any(item is None for item in items):
        return False
    majors = [item.browser_major for item in items if item is not None]
    return majors == [majors[0], majors[0] - 1, majors[0] - 2]


def _validate_accessibility(item: AccessibilityCertification) -> None:
    payload = asdict(item)
    for key, value in payload.items():
        if key.endswith("_ref") and not _optional_ref(value):
            raise ValueError("Accessibility review references must use bounded safe identifiers")
        if key.endswith("_passed") and not isinstance(value, bool):
            raise ValueError("Accessibility pass results must be booleans")
    if (
        isinstance(item.blocking_issue_count, bool)
        or not isinstance(item.blocking_issue_count, int)
        or item.blocking_issue_count < 0
    ):
        raise ValueError("Blocking issue count must be a non-negative integer")


def _review_ref(value: Any) -> bool:
    return isinstance(value, str) and _EVIDENCE_REF.fullmatch(value) is not None


def _optional_ref(value: Any) -> bool:
    return value == "" or _review_ref(value)


def load_certification_bundle(
    path: Path,
) -> tuple[
    str,
    str,
    list[BrowserCertification],
    AccessibilityCertification,
    str,
    str,
]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Could not read the client certification bundle") from error
    expected_fields = {
        "schema_version",
        "release_version",
        "tested_commit_sha",
        "browser_matrix",
        "accessibility",
        "browser_version_review_ref",
        "client_certification_review_ref",
    }
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise ValueError("Client certification bundle fields do not match the exact schema")
    if payload.get("schema_version") != STUDY_SCHEMA_VERSION:
        raise ValueError("Unsupported client certification bundle schema")
    try:
        browser_matrix = [BrowserCertification(**item) for item in payload["browser_matrix"]]
        accessibility = AccessibilityCertification(**payload["accessibility"])
    except (TypeError, KeyError) as error:
        raise ValueError("Invalid client certification bundle records") from error
    return (
        payload["release_version"],
        payload["tested_commit_sha"],
        browser_matrix,
        accessibility,
        payload["browser_version_review_ref"],
        payload["client_certification_review_ref"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a fail-closed browser and accessibility certification report"
    )
    parser.add_argument("certification_bundle", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    (
        release_version,
        tested_commit_sha,
        browser_matrix,
        accessibility,
        browser_version_review_ref,
        client_certification_review_ref,
    ) = load_certification_bundle(arguments.certification_bundle)
    report = build_client_certification_report(
        release_version=release_version,
        tested_commit_sha=tested_commit_sha,
        browser_matrix=browser_matrix,
        accessibility=accessibility,
        browser_version_review_ref=browser_version_review_ref,
        client_certification_review_ref=client_certification_review_ref,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
