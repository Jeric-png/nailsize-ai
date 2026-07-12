import importlib.util
import json
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPOSITORY_ROOT / "services/inference/scripts/release_readiness.py"
SPEC = importlib.util.spec_from_file_location("release_readiness", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
READINESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(READINESS)

COMMIT = "a" * 40
MODEL_SHA = "b" * 64
DIGEST = "c" * 64
SOURCE_IMAGE = (
    f"asia-docker.pkg.dev/nailsize-staging/nailsize-staging-inference/inference@sha256:{DIGEST}"
)
DESTINATION_IMAGE = (
    f"asia-docker.pkg.dev/nailsize-production/nailsize-production-inference/"
    f"inference@sha256:{DIGEST}"
)


def evidence_payloads():
    refs = {
        field: f"evidence:{field}"
        for field in READINESS.PRODUCTION_CONTROL_FIELDS
        if field.endswith("_ref")
    }
    controls = {
        **refs,
        "retention_days": 30,
        **{
            field: True
            for field in READINESS.PRODUCTION_CONTROL_FIELDS
            if not field.endswith("_ref") and field != "retention_days"
        },
    }
    security = {
        **{
            field: f"evidence:{field}"
            for field in READINESS.SECURITY_FIELDS
            if field.endswith("_ref")
        },
        **{field: 0 for field in READINESS.SECURITY_FIELDS if field.endswith("_count")},
    }
    return {
        "model-release-manifest.json": {
            "schema_version": "nailsize-model-release@7",
            "model_version": "model-2026-07",
            "model_sha256": MODEL_SHA,
            "approved": True,
        },
        "github-environment-audit.json": {
            "schema_version": "nailsize-github-environment-audit@1",
            "repository": "Jeric-png/nailsize-ai",
            "passed": True,
        },
        "staging-promotion.json": {
            "schema_version": "nailsize-staging-promotion@1",
            "git_commit_sha": COMMIT,
            "model_release_tag": "model-release-v1",
            "model_version": "model-2026-07",
            "model_sha256": MODEL_SHA,
            "staging_image_uri": SOURCE_IMAGE,
            "passed": True,
        },
        "deployment-manifest.json": {
            "schema_version": "nailsize-deployment@3",
            "environment": "production",
            "git_commit_sha": COMMIT,
            "api_url": "https://api.nailsize.example",
            "frontend_url": "https://nailsize.example",
            "image_uri": DESTINATION_IMAGE,
            "promoted_from_image_uri": SOURCE_IMAGE,
            "model_release_tag": "model-release-v1",
            "model_version": "model-2026-07",
            "model_sha256": MODEL_SHA,
        },
        "onnx-runtime-benchmark.json": {
            "schema_version": "nailsize-cloud-run-onnx-benchmark@1",
            "environment": "production",
            "model_version": "model-2026-07",
            "model_sha256": MODEL_SHA,
            "image_uri": DESTINATION_IMAGE,
            "passed": True,
        },
        "runtime-model-verification.json": {
            "schema_version": "nailsize-runtime-model-verification@1",
            "model_version": "model-2026-07",
            "model_sha256": MODEL_SHA,
            "status": "ready",
        },
        "image-promotion.json": {
            "schema_version": "nailsize-image-promotion@1",
            "source_image_uri": SOURCE_IMAGE,
            "destination_image_uri": DESTINATION_IMAGE,
            "digest": f"sha256:{DIGEST}",
            "passed": True,
        },
        "vercel-deployment.json": {
            "schema_version": "nailsize-vercel-deployment@1",
            "git_commit_sha": COMMIT,
            "frontend_url": "https://nailsize.example",
            "target": "production",
            "ready_state": "READY",
            "ready_substate": "PROMOTED",
        },
        "deployment-smoke.json": {
            "schema_version": "nailsize-deployment-smoke@2",
            "environment": "production",
            "frontend_host": "nailsize.example",
            "api_host": "api.nailsize.example",
            "expected_model_version": "model-2026-07",
            "checks": [
                {"name": name, "passed": True} for name in sorted(READINESS.EXPECTED_SMOKE_CHECKS)
            ],
            "passed": True,
        },
        "client-certification.json": {
            "schema_version": "nailsize-client-certification@1",
            "release_version": "release-2026-07",
            "tested_commit_sha": COMMIT,
            "decision": "client_validation_passed",
            "public_launch_may_continue": True,
            "passed": True,
        },
        "privacy-release-boundary.json": {
            "schema_version": "nailsize-privacy-release-boundary@1",
            "passed": True,
        },
        "release-attestations.json": {
            "schema_version": READINESS.ATTESTATION_SCHEMA_VERSION,
            "release_version": "release-2026-07",
            "repository": "Jeric-png/nailsize-ai",
            "git_commit_sha": COMMIT,
            "production_controls": controls,
            "security_and_defects": security,
            "signoffs": {field: f"evidence:{field}" for field in READINESS.SIGNOFF_FIELDS},
        },
    }


def write_bundle(path: Path, payloads=None):
    path.mkdir()
    for name, payload in (payloads or evidence_payloads()).items():
        (path / name).write_text(json.dumps(payload), encoding="utf-8")


def test_complete_identity_linked_evidence_is_release_ready(tmp_path) -> None:
    bundle = tmp_path / "release"
    write_bundle(bundle)

    report = READINESS.build_release_readiness_report(bundle)

    assert report["passed"] is True
    assert report["decision"] == "release_ready"
    assert report["public_launch_may_continue"] is True
    assert report["evidence_complete"] is True
    assert report["failed_checks"] == []
    assert report["missing_evidence"] == []
    assert all(report["schema_checks"].values())
    assert all(report["checks"].values())
    assert set(report["evidence_sha256"]) == READINESS.REQUIRED_FILENAMES
    assert all(len(value) == 64 for value in report["evidence_sha256"].values())


def test_missing_accountable_reference_is_insufficient_evidence(tmp_path) -> None:
    payloads = evidence_payloads()
    payloads["release-attestations.json"]["signoffs"]["nail_tech_signoff_ref"] = ""
    bundle = tmp_path / "release"
    write_bundle(bundle, payloads)

    report = READINESS.build_release_readiness_report(bundle)

    assert report["decision"] == "insufficient_evidence"
    assert report["passed"] is False
    assert report["missing_evidence"] == ["signoffs.nail_tech_signoff_ref"]
    assert report["checks"]["accountable_evidence_complete"] is False


@pytest.mark.parametrize(
    ("filename", "field", "value", "failed_check"),
    [
        ("model-release-manifest.json", "approved", False, "model_release_approved"),
        ("onnx-runtime-benchmark.json", "passed", False, "production_benchmark_passed"),
        ("deployment-smoke.json", "passed", False, "production_smoke_passed"),
        ("privacy-release-boundary.json", "passed", False, "source_privacy_boundary_passed"),
    ],
)
def test_complete_failing_evidence_blocks_release(
    tmp_path, filename, field, value, failed_check
) -> None:
    payloads = evidence_payloads()
    payloads[filename][field] = value
    bundle = tmp_path / "release"
    write_bundle(bundle, payloads)

    report = READINESS.build_release_readiness_report(bundle)

    assert report["decision"] == "release_blocked"
    assert report["evidence_complete"] is True
    assert failed_check in report["failed_checks"]
    assert report["public_launch_may_continue"] is False


def test_identity_mismatch_and_nonzero_security_issue_block_release(tmp_path) -> None:
    payloads = evidence_payloads()
    payloads["vercel-deployment.json"]["git_commit_sha"] = "d" * 40
    payloads["release-attestations.json"]["security_and_defects"]["high_vulnerability_count"] = 1
    bundle = tmp_path / "release"
    write_bundle(bundle, payloads)

    report = READINESS.build_release_readiness_report(bundle)

    assert report["decision"] == "release_blocked"
    assert report["checks"]["identity_chain_consistent"] is False
    assert report["checks"]["security_and_defects_clear"] is False


def test_missing_image_host_or_wrong_repository_cannot_compare_equal(tmp_path) -> None:
    payloads = evidence_payloads()
    payloads["image-promotion.json"]["source_image_uri"] = None
    payloads["image-promotion.json"]["destination_image_uri"] = None
    payloads["image-promotion.json"]["digest"] = None
    payloads["deployment-manifest.json"]["frontend_url"] = None
    payloads["deployment-manifest.json"]["api_url"] = None
    payloads["deployment-manifest.json"]["image_uri"] = None
    payloads["deployment-manifest.json"]["promoted_from_image_uri"] = None
    payloads["github-environment-audit.json"]["repository"] = "someone/else"
    bundle = tmp_path / "release"
    write_bundle(bundle, payloads)

    report = READINESS.build_release_readiness_report(bundle)

    assert report["decision"] == "release_blocked"
    assert report["checks"]["identity_chain_consistent"] is False


def test_incomplete_smoke_contract_and_bad_production_control_block(tmp_path) -> None:
    payloads = evidence_payloads()
    payloads["deployment-smoke.json"]["checks"].pop()
    payloads["release-attestations.json"]["production_controls"]["retention_days"] = 31
    bundle = tmp_path / "release"
    write_bundle(bundle, payloads)

    report = READINESS.build_release_readiness_report(bundle)

    assert report["decision"] == "release_blocked"
    assert report["checks"]["production_smoke_passed"] is False
    assert report["checks"]["production_controls_passed"] is False


def test_exact_file_and_attestation_schemas_reject_extra_or_private_data(tmp_path) -> None:
    missing_bundle = tmp_path / "missing"
    payloads = evidence_payloads()
    payloads.pop("client-certification.json")
    write_bundle(missing_bundle, payloads)
    with pytest.raises(ValueError, match="files do not match contract"):
        READINESS.build_release_readiness_report(missing_bundle)

    private_bundle = tmp_path / "private"
    payloads = evidence_payloads()
    payloads["release-attestations.json"]["reviewer_email"] = "private@example.com"
    write_bundle(private_bundle, payloads)
    with pytest.raises(ValueError, match="exact schema"):
        READINESS.build_release_readiness_report(private_bundle)

    invalid_ref_bundle = tmp_path / "invalid-ref"
    payloads = evidence_payloads()
    payloads["release-attestations.json"]["signoffs"]["product_signoff_ref"] = "private@example.com"
    write_bundle(invalid_ref_bundle, payloads)
    with pytest.raises(ValueError, match="references"):
        READINESS.build_release_readiness_report(invalid_ref_bundle)


def test_malformed_identifiers_and_boolean_counts_are_rejected(tmp_path) -> None:
    bad_commit = evidence_payloads()
    bad_commit["release-attestations.json"]["git_commit_sha"] = "main"
    bundle = tmp_path / "bad-commit"
    write_bundle(bundle, bad_commit)
    with pytest.raises(ValueError, match="40-character"):
        READINESS.build_release_readiness_report(bundle)

    boolean_count = evidence_payloads()
    boolean_count["release-attestations.json"]["security_and_defects"][
        "critical_vulnerability_count"
    ] = False
    bundle = tmp_path / "boolean-count"
    write_bundle(bundle, boolean_count)
    with pytest.raises(ValueError, match="counts"):
        READINESS.build_release_readiness_report(bundle)
