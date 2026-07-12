import copy

import pytest

from scripts.verify_staging_promotion import EXPECTED_SMOKE_CHECKS, verify_staging_promotion

RUN_ID = "29165365931"
COMMIT_SHA = "a" * 40
MODEL_VERSION = "nailsize-20260712"
MODEL_RELEASE_TAG = "model-nailsize-20260712"
MODEL_SHA256 = "b" * 64
VERCEL_TEAM_ID = "team_Y3lABiHAH20CFfuXAql7s7J1"
GITHUB_REPOSITORY = "Jeric-png/nailsize-ai"
GITHUB_REPOSITORY_ID = "1297575199"
FRONTEND = "https://staging.nailsize.example"
API = "https://api-staging.nailsize.example"
IMAGE = (
    "us-central1-docker.pkg.dev/nailsize-staging/"
    "nailsize-staging-inference/inference@sha256:" + "c" * 64
)


def _evidence():
    return {
        "run_metadata": {
            "databaseId": int(RUN_ID),
            "workflowName": "Deploy verified release",
            "event": "workflow_dispatch",
            "headBranch": "main",
            "headSha": COMMIT_SHA,
            "status": "completed",
            "conclusion": "success",
        },
        "deployment_manifest": {
            "schema_version": "nailsize-deployment@3",
            "environment": "staging",
            "promoted_from_image_uri": None,
            "git_commit_sha": COMMIT_SHA,
            "model_release_tag": MODEL_RELEASE_TAG,
            "api_url": API,
            "frontend_url": FRONTEND,
            "image_uri": IMAGE,
            "model_version": MODEL_VERSION,
            "model_sha256": MODEL_SHA256,
        },
        "benchmark_report": {
            "schema_version": "nailsize-cloud-run-onnx-benchmark@1",
            "environment": "staging",
            "cloud_run_job": "nailsize-staging-onnx-benchmark",
            "cloud_run_execution": "nailsize-staging-onnx-benchmark-abc12",
            "image_uri": IMAGE,
            "model_version": MODEL_VERSION,
            "model_sha256": MODEL_SHA256,
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
            "latency_ms": {"p50": 80.0, "p95": 100.0, "p99": 120.0, "mean": 85.0},
            "limits_ms": {"p50": 2000.0, "p95": 5000.0, "p99": 10000.0},
            "checks": {
                "immutable_image": True,
                "selected_model": True,
                "cloud_run_job_contract": True,
                "successful_single_task": True,
                "structured_sample_linked": True,
                "cpu_tensor_contract": True,
                "finite_outputs": True,
                "necessary_latency_limits": True,
            },
            "passed": True,
        },
        "vercel_project_audit": {
            "schema_version": "nailsize-vercel-project-audit@1",
            "team_id": VERCEL_TEAM_ID,
            "github_repository": GITHUB_REPOSITORY,
            "github_repository_id": GITHUB_REPOSITORY_ID,
            "projects": [
                {
                    "project_id": "prj_lbY1CKeNkc7RZU0mphHVHEX8OMXp",
                    "project_name": "nailsize-ai-staging",
                    "release_settings_match": True,
                    "git_settings_match": True,
                    "privacy_settings_match": True,
                    "web_analytics_enabled": False,
                    "integration_count": 0,
                    "configured_environment_variable_names": [],
                    "passed": True,
                }
            ],
            "passed": True,
        },
        "vercel_deployment": {
            "schema_version": "nailsize-vercel-deployment@1",
            "deployment_id": "dpl_staging123",
            "frontend_url": FRONTEND,
            "git_commit_sha": COMMIT_SHA,
            "target": "production",
            "ready_state": "READY",
            "ready_substate": "PROMOTED",
        },
        "smoke_report": {
            "schema_version": "nailsize-deployment-smoke@2",
            "environment": "staging",
            "frontend_host": "staging.nailsize.example",
            "api_host": "api-staging.nailsize.example",
            "expected_model_version": MODEL_VERSION,
            "checks": [
                {"name": name, "passed": True, "status_code": 200, "result": "verified"}
                for name in sorted(EXPECTED_SMOKE_CHECKS)
            ],
            "passed": True,
        },
    }


def _verify(evidence):
    return verify_staging_promotion(
        **evidence,
        expected_run_id=RUN_ID,
        expected_commit_sha=COMMIT_SHA,
        expected_model_release_tag=MODEL_RELEASE_TAG,
        expected_model_version=MODEL_VERSION,
        expected_model_sha256=MODEL_SHA256,
        expected_vercel_team_id=VERCEL_TEAM_ID,
        expected_github_repository=GITHUB_REPOSITORY,
        expected_github_repository_id=GITHUB_REPOSITORY_ID,
    )


def test_accepts_exact_successful_staging_candidate() -> None:
    report = _verify(_evidence())

    assert report["passed"] is True
    assert report["staging_run_id"] == RUN_ID
    assert report["git_commit_sha"] == COMMIT_SHA
    assert report["smoke_checks_passed"] == 7
    assert report["staging_benchmark_execution"] == "nailsize-staging-onnx-benchmark-abc12"
    assert report["staging_vercel_deployment_id"] == "dpl_staging123"


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("run_metadata", "conclusion", "failure"),
        ("run_metadata", "headSha", "d" * 40),
        ("deployment_manifest", "environment", "production"),
        ("deployment_manifest", "promoted_from_image_uri", "staging-image"),
        ("deployment_manifest", "model_sha256", "e" * 64),
        ("benchmark_report", "passed", False),
        ("benchmark_report", "image_uri", "different"),
        ("vercel_project_audit", "passed", False),
        ("vercel_project_audit", "team_id", "team_wrong"),
        ("vercel_deployment", "ready_substate", "STAGED"),
        ("smoke_report", "passed", False),
        ("smoke_report", "schema_version", "nailsize-deployment-smoke@1"),
        ("smoke_report", "expected_model_version", "different-model"),
    ],
)
def test_rejects_mismatched_or_failed_staging_evidence(section, field, value) -> None:
    evidence = _evidence()
    evidence[section][field] = value

    with pytest.raises(ValueError):
        _verify(evidence)


def test_rejects_missing_duplicate_or_failed_smoke_checks() -> None:
    for mutate in ("missing", "duplicate", "failed"):
        evidence = copy.deepcopy(_evidence())
        checks = evidence["smoke_report"]["checks"]
        if mutate == "missing":
            checks.pop()
        elif mutate == "duplicate":
            checks[-1] = copy.deepcopy(checks[0])
        else:
            checks[0]["passed"] = False
        with pytest.raises(ValueError, match="smoke"):
            _verify(evidence)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_name", "nailsize-ai-production"),
        ("release_settings_match", False),
        ("git_settings_match", False),
        ("privacy_settings_match", False),
        ("web_analytics_enabled", True),
        ("integration_count", 1),
        ("configured_environment_variable_names", ["SECRET"]),
        ("passed", False),
    ],
)
def test_rejects_failed_or_wrong_staging_vercel_project_controls(field, value) -> None:
    evidence = _evidence()
    evidence["vercel_project_audit"]["projects"][0][field] = value

    with pytest.raises(ValueError, match="Vercel project"):
        _verify(evidence)


def test_rejects_extra_vercel_project_audit_fields() -> None:
    evidence = _evidence()
    evidence["vercel_project_audit"]["unexpected_private_field"] = "unexpected"

    with pytest.raises(ValueError, match="Vercel project audit"):
        _verify(evidence)


@pytest.mark.parametrize(
    "overrides",
    [
        {"expected_run_id": "main"},
        {"expected_commit_sha": "main"},
        {"expected_model_release_tag": "model release"},
        {"expected_model_version": "synthetic version"},
        {"expected_model_sha256": "not-a-sha"},
        {"expected_vercel_team_id": "team invalid"},
        {"expected_github_repository": "repository-only"},
        {"expected_github_repository_id": "not-numeric"},
    ],
)
def test_rejects_ambiguous_expected_identifiers(overrides) -> None:
    arguments = {
        **_evidence(),
        "expected_run_id": RUN_ID,
        "expected_commit_sha": COMMIT_SHA,
        "expected_model_release_tag": MODEL_RELEASE_TAG,
        "expected_model_version": MODEL_VERSION,
        "expected_model_sha256": MODEL_SHA256,
        "expected_vercel_team_id": VERCEL_TEAM_ID,
        "expected_github_repository": GITHUB_REPOSITORY,
        "expected_github_repository_id": GITHUB_REPOSITORY_ID,
    }
    arguments.update(overrides)
    with pytest.raises(ValueError):
        verify_staging_promotion(**arguments)
