import copy

import pytest

from scripts.verify_staging_promotion import EXPECTED_SMOKE_CHECKS, verify_staging_promotion

RUN_ID = "29165365931"
COMMIT_SHA = "a" * 40
MODEL_VERSION = "nailsize-20260712"
MODEL_RELEASE_TAG = "model-nailsize-20260712"
MODEL_SHA256 = "b" * 64
FRONTEND = "https://staging.nailsize.example"
API = "https://api-staging.nailsize.example"


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
            "image_uri": (
                "us-central1-docker.pkg.dev/nailsize-staging/"
                "nailsize-staging-inference/inference@sha256:" + "c" * 64
            ),
            "model_version": MODEL_VERSION,
            "model_sha256": MODEL_SHA256,
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
    )


def test_accepts_exact_successful_staging_candidate() -> None:
    report = _verify(_evidence())

    assert report["passed"] is True
    assert report["staging_run_id"] == RUN_ID
    assert report["git_commit_sha"] == COMMIT_SHA
    assert report["smoke_checks_passed"] == 7
    assert report["staging_vercel_deployment_id"] == "dpl_staging123"


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("run_metadata", "conclusion", "failure"),
        ("run_metadata", "headSha", "d" * 40),
        ("deployment_manifest", "environment", "production"),
        ("deployment_manifest", "promoted_from_image_uri", "staging-image"),
        ("deployment_manifest", "model_sha256", "e" * 64),
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
    "overrides",
    [
        {"expected_run_id": "main"},
        {"expected_commit_sha": "main"},
        {"expected_model_release_tag": "model release"},
        {"expected_model_version": "synthetic version"},
        {"expected_model_sha256": "not-a-sha"},
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
    }
    arguments.update(overrides)
    with pytest.raises(ValueError):
        verify_staging_promotion(**arguments)
