import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

EXPECTED_SMOKE_CHECKS = frozenset(
    {
        "api_health",
        "api_readiness",
        "cors_trusted_origin",
        "cors_untrusted_origin",
        "malformed_upload_rejected",
        "frontend_security_headers",
    }
)


def verify_staging_promotion(
    *,
    run_metadata: dict[str, Any],
    deployment_manifest: dict[str, Any],
    vercel_deployment: dict[str, Any],
    smoke_report: dict[str, Any],
    expected_run_id: str,
    expected_commit_sha: str,
    expected_model_release_tag: str,
    expected_model_version: str,
    expected_model_sha256: str,
) -> dict[str, Any]:
    _validate_identifiers(
        expected_run_id,
        expected_commit_sha,
        expected_model_release_tag,
        expected_model_version,
        expected_model_sha256,
    )
    if (
        str(run_metadata.get("databaseId")) != expected_run_id
        or run_metadata.get("workflowName") != "Deploy verified release"
        or run_metadata.get("event") != "workflow_dispatch"
        or run_metadata.get("headBranch") != "main"
        or run_metadata.get("headSha") != expected_commit_sha
        or run_metadata.get("status") != "completed"
        or run_metadata.get("conclusion") != "success"
    ):
        raise ValueError("Staging workflow run is not the exact successful release candidate")

    if (
        deployment_manifest.get("schema_version") != "nailsize-deployment@2"
        or deployment_manifest.get("environment") != "staging"
        or deployment_manifest.get("git_commit_sha") != expected_commit_sha
        or deployment_manifest.get("model_release_tag") != expected_model_release_tag
        or deployment_manifest.get("model_version") != expected_model_version
        or deployment_manifest.get("model_sha256") != expected_model_sha256
    ):
        raise ValueError("Staging deployment manifest does not match the production candidate")
    frontend_url = _exact_https_origin(deployment_manifest.get("frontend_url"), "frontend URL")
    api_url = _exact_https_origin(deployment_manifest.get("api_url"), "API URL")
    image_uri = deployment_manifest.get("image_uri")
    if not isinstance(image_uri, str) or not re.fullmatch(
        r"[A-Za-z0-9._/-]+@sha256:[0-9a-f]{64}", image_uri
    ):
        raise ValueError("Staging image must be identified by an immutable digest")

    if (
        vercel_deployment.get("schema_version") != "nailsize-vercel-deployment@1"
        or vercel_deployment.get("git_commit_sha") != expected_commit_sha
        or vercel_deployment.get("frontend_url") != frontend_url
        or vercel_deployment.get("target") != "production"
        or vercel_deployment.get("ready_state") != "READY"
        or vercel_deployment.get("ready_substate") != "PROMOTED"
        or not isinstance(vercel_deployment.get("deployment_id"), str)
        or not vercel_deployment["deployment_id"]
    ):
        raise ValueError("Staging Vercel deployment is not the exact promoted release candidate")

    checks = smoke_report.get("checks")
    if (
        smoke_report.get("schema_version") != "nailsize-deployment-smoke@1"
        or smoke_report.get("environment") != "staging"
        or smoke_report.get("expected_model_version") != expected_model_version
        or smoke_report.get("frontend_host") != urlparse(frontend_url).hostname
        or smoke_report.get("api_host") != urlparse(api_url).hostname
        or smoke_report.get("passed") is not True
        or not isinstance(checks, list)
    ):
        raise ValueError("Staging smoke report does not match the production candidate")
    observed_names: list[str] = []
    for check in checks:
        if not isinstance(check, dict) or check.get("passed") is not True:
            raise ValueError("Every staging smoke check must pass")
        name = check.get("name")
        if not isinstance(name, str):
            raise ValueError("Staging smoke check names must be strings")
        observed_names.append(name)
    if (
        len(observed_names) != len(set(observed_names))
        or set(observed_names) != EXPECTED_SMOKE_CHECKS
    ):
        raise ValueError("Staging smoke report must contain the exact required checks")

    return {
        "schema_version": "nailsize-staging-promotion@1",
        "staging_run_id": expected_run_id,
        "git_commit_sha": expected_commit_sha,
        "model_release_tag": expected_model_release_tag,
        "model_version": expected_model_version,
        "model_sha256": expected_model_sha256,
        "staging_frontend_host": urlparse(frontend_url).hostname,
        "staging_api_host": urlparse(api_url).hostname,
        "staging_image_uri": image_uri,
        "staging_vercel_deployment_id": vercel_deployment["deployment_id"],
        "smoke_checks_passed": len(observed_names),
        "passed": True,
    }


def _validate_identifiers(
    run_id: str,
    commit_sha: str,
    model_release_tag: str,
    model_version: str,
    model_sha256: str,
) -> None:
    if not run_id.isdigit() or run_id.startswith("0"):
        raise ValueError("Staging workflow run ID must be a positive integer")
    if len(commit_sha) != 40 or any(
        character not in "0123456789abcdef" for character in commit_sha
    ):
        raise ValueError("Commit SHA must be 40 lowercase hexadecimal characters")
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"
    for value, label in (
        (model_release_tag, "Model release tag"),
        (model_version, "Model version"),
    ):
        if (
            not value
            or len(value) > 128
            or not value[0].isalnum()
            or any(character not in allowed for character in value)
        ):
            raise ValueError(f"{label} is invalid")
    if len(model_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in model_sha256
    ):
        raise ValueError("Model SHA-256 must be lowercase hexadecimal")


def _exact_https_origin(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Staging {label} must be an exact HTTPS origin")
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"Staging {label} must be an exact HTTPS origin")
    return value.rstrip("/")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read staging evidence: {path.name}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"Staging evidence must be a JSON object: {path.name}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Require an exact successful staging deployment before production promotion"
    )
    parser.add_argument("--run-metadata", required=True, type=Path)
    parser.add_argument("--deployment-manifest", required=True, type=Path)
    parser.add_argument("--vercel-deployment", required=True, type=Path)
    parser.add_argument("--smoke-report", required=True, type=Path)
    parser.add_argument("--expected-run-id", required=True)
    parser.add_argument("--expected-commit-sha", required=True)
    parser.add_argument("--expected-model-release-tag", required=True)
    parser.add_argument("--expected-model-version", required=True)
    parser.add_argument("--expected-model-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        report = verify_staging_promotion(
            run_metadata=_read_json(arguments.run_metadata),
            deployment_manifest=_read_json(arguments.deployment_manifest),
            vercel_deployment=_read_json(arguments.vercel_deployment),
            smoke_report=_read_json(arguments.smoke_report),
            expected_run_id=arguments.expected_run_id,
            expected_commit_sha=arguments.expected_commit_sha,
            expected_model_release_tag=arguments.expected_model_release_tag,
            expected_model_version=arguments.expected_model_version,
            expected_model_sha256=arguments.expected_model_sha256,
        )
    except ValueError as error:
        parser.error(str(error))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
