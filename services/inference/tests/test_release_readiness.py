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
            "checkpoint_sha256": "d" * 64,
            "model_version": "model-2026-07",
            "model_sha256": MODEL_SHA,
            "onnx_parity_max_abs_error": 0.00001,
            "dataset_version": "dataset-2026-07",
            "dataset_provenance_sha256": "e" * 64,
            "holdout_lock_sha256": "f" * 64,
            "segmentation_evaluation_sha256": "1" * 64,
            "chart_id": "platform-default",
            "chart_version": "1",
            "segmentation_boundary_error_px": 1.2,
            "accuracy_participant_count": 200,
            "accuracy_nail_count": 2000,
            "annotation_paired_item_count": 200,
            "annotation_paired_participant_count": 20,
            "size_calibration_participant_count": 200,
            "size_calibration_nail_count": 2000,
            "operational_participant_count": 200,
            "approved": True,
        },
        "github-environment-audit.json": environment_audit(),
        "staging-promotion.json": {
            "schema_version": "nailsize-staging-promotion@1",
            "staging_run_id": "12345",
            "git_commit_sha": COMMIT,
            "model_release_tag": "model-release-v1",
            "model_version": "model-2026-07",
            "model_sha256": MODEL_SHA,
            "staging_frontend_host": "staging.nailsize.example",
            "staging_api_host": "api-staging.nailsize.example",
            "staging_image_uri": SOURCE_IMAGE,
            "staging_benchmark_execution": "nailsize-staging-onnx-benchmark-abc123",
            "staging_vercel_deployment_id": "vercel-staging-1",
            "smoke_checks_passed": 7,
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
            "cloud_run_job": "nailsize-production-onnx-benchmark",
            "cloud_run_execution": "nailsize-production-onnx-benchmark-abc123",
            "image_uri": DESTINATION_IMAGE,
            "model_version": "model-2026-07",
            "model_sha256": MODEL_SHA,
            "provider": "CPUExecutionProvider",
            "iterations": 200,
            "warmup_iterations": 20,
            "input_shape": [1, 3, 224, 160],
            "output_shape": [1, 1, 224, 160],
            "runtime_contract": {
                "cpu": "2",
                "memory": "4Gi",
                "execution_environment": "gen2",
                "task_count": 1,
                "parallelism": 1,
                "max_retries": 0,
                "timeout_seconds": 300,
            },
            "latency_ms": {"p50": 100.0, "p95": 200.0, "p99": 300.0},
            "limits_ms": {"p50": 2000.0, "p95": 5000.0, "p99": 10000.0},
            "checks": {field: True for field in READINESS.BENCHMARK_CHECK_FIELDS},
            "passed": True,
        },
        "runtime-model-verification.json": {
            "schema_version": "nailsize-runtime-model-verification@1",
            "model_version": "model-2026-07",
            "model_sha256": MODEL_SHA,
            "runtime_provider": "CPUExecutionProvider",
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
            "deployment_id": "vercel-production-1",
            "generated_url": "https://generated.nailsize.example",
            "frontend_url": "https://nailsize.example",
            "git_commit_sha": COMMIT,
            "project_id": "project-production-1",
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
                {
                    "name": name,
                    "passed": True,
                    "status_code": 200,
                    "result": READINESS.EXPECTED_SMOKE_RESULTS[name],
                }
                for name in sorted(READINESS.EXPECTED_SMOKE_CHECKS)
            ],
            "passed": True,
        },
        "client-certification.json": client_certification(),
        "privacy-release-boundary.json": {
            "schema_version": "nailsize-privacy-release-boundary@1",
            "scope": "source-managed-runtime-and-infrastructure",
            "web_runtime_dependency_count": 4,
            "inference_runtime_dependency_count": 10,
            "terraform_resource_count": 28,
            "terraform_resource_type_count": 20,
            "terraform_log_field_count": 8,
            "container_access_log_disabled": True,
            "load_balancer_metadata_logging_only": True,
            "browser_payload_url_fields": 0,
            "third_party_browser_script_origins": 0,
            "persistent_payload_service_types": 0,
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


def environment_audit():
    deployment_environments = []
    for name in ("staging", "production"):
        deployment_environments.append(
            {
                "name": name,
                "exists": True,
                "required_reviewer_count": 1,
                "prevent_self_review": name == "production",
                "deployment_branch_names": ["main"],
                "configured_variable_names": ["API_DOMAIN"],
                "missing_variable_names": [],
                "unexpected_variable_names": [],
                "configured_secret_names": ["VERCEL_TOKEN"],
                "missing_secret_names": [],
                "unexpected_secret_names": [],
                "passed": True,
            }
        )
    return {
        "schema_version": "nailsize-github-environment-audit@1",
        "repository": "Jeric-png/nailsize-ai",
        "expected_environment_names": ["development", "staging", "production"],
        "unexpected_environment_names": [],
        "environments": [
            {
                "name": "development",
                "exists": True,
                "configured_variable_names": [],
                "configured_secret_names": [],
                "passed": True,
            },
            *deployment_environments,
        ],
        "passed": True,
    }


def client_certification():
    return {
        "schema_version": "nailsize-client-certification@1",
        "release_version": "release-2026-07",
        "tested_commit_sha": COMMIT,
        "required_platforms": list(READINESS.BROWSER_PLATFORMS),
        "required_version_slots": list(READINESS.BROWSER_VERSION_SLOTS),
        "browser_version_review_ref": "review:browser-versions",
        "client_certification_review_ref": "review:client-certification",
        "certification_review_present": True,
        "browser_matrix": [
            {
                "platform": platform,
                "version_slot": slot,
                "browser_major": 130 - index,
                "execution_environment": (
                    "physical_device"
                    if platform in {"ios_safari", "android_chrome"}
                    else "hosted_real_browser"
                ),
                "run_ref": f"run:{platform}:{slot}",
                "passed": True,
            }
            for platform in READINESS.BROWSER_PLATFORMS
            for index, slot in enumerate(READINESS.BROWSER_VERSION_SLOTS)
        ],
        "missing_browser_requirements": [],
        "consecutive_version_coverage": {
            platform: True for platform in READINESS.BROWSER_PLATFORMS
        },
        "browser_evidence_complete": True,
        "browser_passed": True,
        "accessibility": {
            "automated_mobile_scan_ref": "scan:axe-mobile",
            "automated_mobile_passed": True,
            "automated_desktop_scan_ref": "scan:axe-desktop",
            "automated_desktop_passed": True,
            "keyboard_review_ref": "review:keyboard",
            "keyboard_passed": True,
            "voiceover_review_ref": "review:voiceover",
            "voiceover_passed": True,
            "talkback_review_ref": "review:talkback",
            "talkback_passed": True,
            "blocking_issue_count": 0,
            "accessibility_review_ref": "review:accessibility",
            "checks": {
                "automated_mobile": True,
                "automated_desktop": True,
                "keyboard": True,
                "voiceover": True,
                "talkback": True,
                "zero_blocking_issues": True,
            },
            "evidence_complete": True,
            "passed": True,
        },
        "decision": "client_validation_passed",
        "public_launch_may_continue": True,
        "passed": True,
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

    assert report["decision"] == "insufficient_evidence"
    assert report["checks"]["production_smoke_passed"] is False
    assert report["checks"]["production_controls_passed"] is False


def test_extra_top_level_or_nested_artifact_fields_are_insufficient(tmp_path) -> None:
    artifact_names = {
        "model-release-manifest.json": "model_release",
        "github-environment-audit.json": "environment_audit",
        "staging-promotion.json": "staging_promotion",
        "deployment-manifest.json": "production_deployment",
        "onnx-runtime-benchmark.json": "production_benchmark",
        "runtime-model-verification.json": "runtime_model",
        "image-promotion.json": "image_promotion",
        "vercel-deployment.json": "vercel_deployment",
        "deployment-smoke.json": "production_smoke",
        "client-certification.json": "client_certification",
        "privacy-release-boundary.json": "privacy_boundary",
    }
    for index, (filename, schema_name) in enumerate(artifact_names.items()):
        top_level = evidence_payloads()
        top_level[filename]["reviewer_email"] = "private@example.com"
        bundle = tmp_path / f"top-level-{index}"
        write_bundle(bundle, top_level)
        report = READINESS.build_release_readiness_report(bundle)
        assert report["decision"] == "insufficient_evidence"
        assert report["schema_checks"][schema_name] is False

    nested_mutations = (
        ("github-environment-audit.json", "environment_audit", "environments"),
        ("onnx-runtime-benchmark.json", "production_benchmark", "checks"),
        ("deployment-smoke.json", "production_smoke", "checks"),
        ("client-certification.json", "client_certification", "browser_matrix"),
    )
    for index, (filename, schema_name, field) in enumerate(nested_mutations):
        nested = evidence_payloads()
        value = nested[filename][field]
        if isinstance(value, list):
            value[0]["private_payload"] = "private"
        else:
            value["private_payload"] = True
        bundle = tmp_path / f"nested-{index}"
        write_bundle(bundle, nested)
        report = READINESS.build_release_readiness_report(bundle)
        assert report["decision"] == "insufficient_evidence"
        assert report["schema_checks"][schema_name] is False


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
