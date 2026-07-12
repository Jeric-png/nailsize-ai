import importlib.util
import json
from dataclasses import asdict
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPOSITORY_ROOT / "services/inference/scripts/client_certification.py"
SPEC = importlib.util.spec_from_file_location("client_certification", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
CERTIFICATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CERTIFICATION)


def browser_matrix():
    records = []
    for platform_index, platform in enumerate(CERTIFICATION.PLATFORMS):
        current = 130 + platform_index
        for offset, slot in enumerate(CERTIFICATION.VERSION_SLOTS):
            records.append(
                CERTIFICATION.BrowserCertification(
                    platform=platform,
                    version_slot=slot,
                    browser_major=current - offset,
                    execution_environment=(
                        "physical_device"
                        if platform in CERTIFICATION.MOBILE_PLATFORMS
                        else "hosted_real_browser"
                    ),
                    run_ref=f"run-{platform}-{slot}",
                    passed=True,
                )
            )
    return records


def accessibility(**overrides):
    values = {
        "automated_mobile_scan_ref": "axe-mobile-1",
        "automated_mobile_passed": True,
        "automated_desktop_scan_ref": "axe-desktop-1",
        "automated_desktop_passed": True,
        "keyboard_review_ref": "keyboard-review-1",
        "keyboard_passed": True,
        "voiceover_review_ref": "voiceover-review-1",
        "voiceover_passed": True,
        "talkback_review_ref": "talkback-review-1",
        "talkback_passed": True,
        "blocking_issue_count": 0,
        "accessibility_review_ref": "accessibility-review-1",
    }
    values.update(overrides)
    return CERTIFICATION.AccessibilityCertification(**values)


def build(matrix=None, accessibility_result=None, **overrides):
    arguments = {
        "release_version": "release-2026-07",
        "tested_commit_sha": "a" * 40,
        "browser_matrix": browser_matrix() if matrix is None else matrix,
        "accessibility": accessibility() if accessibility_result is None else accessibility_result,
        "browser_version_review_ref": "browser-version-review-1",
        "client_certification_review_ref": "client-certification-review-1",
    }
    arguments.update(overrides)
    return CERTIFICATION.build_client_certification_report(**arguments)


def test_complete_real_browser_and_accessibility_evidence_passes() -> None:
    report = build()

    assert report["passed"] is True
    assert report["decision"] == "client_validation_passed"
    assert report["public_launch_may_continue"] is True
    assert len(report["browser_matrix"]) == 18
    assert not report["missing_browser_requirements"]
    assert all(report["consecutive_version_coverage"].values())
    assert all(report["accessibility"]["checks"].values())


def test_missing_or_nonconsecutive_browser_evidence_is_insufficient() -> None:
    missing = build(browser_matrix()[:-1])
    version_gap = browser_matrix()
    version_gap[1] = CERTIFICATION.BrowserCertification(
        **{**asdict(version_gap[1]), "browser_major": version_gap[1].browser_major - 1}
    )
    nonconsecutive = build(version_gap)

    assert missing["decision"] == "insufficient_evidence"
    assert missing["browser_evidence_complete"] is False
    assert missing["missing_browser_requirements"] == [
        {"platform": "desktop_safari", "version_slot": "previous_2"}
    ]
    assert nonconsecutive["decision"] == "insufficient_evidence"
    assert nonconsecutive["consecutive_version_coverage"]["ios_safari"] is False


def test_complete_failed_browser_or_accessibility_evidence_blocks_launch() -> None:
    failed_matrix = browser_matrix()
    failed_matrix[0] = CERTIFICATION.BrowserCertification(
        **{**asdict(failed_matrix[0]), "passed": False}
    )
    browser_failure = build(failed_matrix)
    accessibility_failure = build(
        accessibility_result=accessibility(voiceover_passed=False, blocking_issue_count=1)
    )

    assert browser_failure["decision"] == "client_validation_failed"
    assert browser_failure["public_launch_may_continue"] is False
    assert accessibility_failure["decision"] == "client_validation_failed"
    assert accessibility_failure["accessibility"]["checks"]["voiceover"] is False
    assert accessibility_failure["accessibility"]["checks"]["zero_blocking_issues"] is False


def test_blank_review_references_are_incomplete_not_success() -> None:
    report = build(accessibility_result=accessibility(talkback_review_ref=""))

    assert report["decision"] == "insufficient_evidence"
    assert report["accessibility"]["evidence_complete"] is False
    assert report["passed"] is False

    with pytest.raises(ValueError, match="review references"):
        build(accessibility_result=accessibility(talkback_review_ref="private@example.com"))

    missing_final_review = build(client_certification_review_ref="")
    assert missing_final_review["decision"] == "insufficient_evidence"
    assert missing_final_review["certification_review_present"] is False


def test_rejects_emulated_mobile_duplicate_slots_and_invalid_commit() -> None:
    emulated = browser_matrix()
    emulated[0] = CERTIFICATION.BrowserCertification(
        **{**asdict(emulated[0]), "execution_environment": "hosted_real_browser"}
    )
    with pytest.raises(ValueError, match="physical device"):
        build(emulated)
    with pytest.raises(ValueError, match="unique"):
        build([*browser_matrix(), browser_matrix()[0]])
    with pytest.raises(ValueError, match="40-character SHA"):
        CERTIFICATION.build_client_certification_report(
            release_version="release-1",
            tested_commit_sha="main",
            browser_matrix=browser_matrix(),
            accessibility=accessibility(),
            browser_version_review_ref="browser-version-review-1",
            client_certification_review_ref="client-certification-review-1",
        )


def test_exact_bundle_loader_rejects_private_or_extra_fields(tmp_path) -> None:
    payload = {
        "schema_version": CERTIFICATION.STUDY_SCHEMA_VERSION,
        "release_version": "release-2026-07",
        "tested_commit_sha": "a" * 40,
        "browser_matrix": [asdict(item) for item in browser_matrix()],
        "accessibility": asdict(accessibility()),
        "browser_version_review_ref": "browser-version-review-1",
        "client_certification_review_ref": "client-certification-review-1",
    }
    path = tmp_path / "client-certification.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = CERTIFICATION.load_certification_bundle(path)
    report = CERTIFICATION.build_client_certification_report(
        release_version=loaded[0],
        tested_commit_sha=loaded[1],
        browser_matrix=loaded[2],
        accessibility=loaded[3],
        browser_version_review_ref=loaded[4],
        client_certification_review_ref=loaded[5],
    )
    rendered = json.dumps(report)

    assert report["passed"] is True
    assert "tester" not in rendered
    assert "participant" not in rendered
    payload["browser_matrix"][0]["tester_email"] = "private@example.com"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid client certification"):
        CERTIFICATION.load_certification_bundle(path)

    payload["browser_matrix"][0].pop("tester_email")
    payload["unexpected"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="exact schema"):
        CERTIFICATION.load_certification_bundle(path)
