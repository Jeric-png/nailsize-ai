"""Build a fail-closed production release-readiness decision."""

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ATTESTATION_SCHEMA_VERSION = "nailsize-release-readiness-attestations@1"
REPORT_SCHEMA_VERSION = "nailsize-release-readiness@1"
REQUIRED_FILENAMES = frozenset(
    {
        "client-certification.json",
        "deployment-manifest.json",
        "deployment-smoke.json",
        "github-environment-audit.json",
        "image-promotion.json",
        "model-release-manifest.json",
        "onnx-runtime-benchmark.json",
        "privacy-release-boundary.json",
        "release-attestations.json",
        "runtime-model-verification.json",
        "staging-promotion.json",
        "vercel-deployment.json",
    }
)
EXPECTED_SMOKE_CHECKS = frozenset(
    {
        "api_health",
        "api_readiness",
        "cors_trusted_origin",
        "cors_untrusted_origin",
        "malformed_upload_rejected",
        "frontend_security_headers",
        "frontend_api_binding",
    }
)
_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_MODEL_SHA = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_EVIDENCE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,511}$")
_DIGEST_IMAGE = re.compile(r"^.+@sha256:(?P<digest>[0-9a-f]{64})$")

PRODUCTION_CONTROL_FIELDS = frozenset(
    {
        "production_revision_ref",
        "infrastructure_review_ref",
        "environment_isolation_review_ref",
        "iam_inspection_ref",
        "logging_inspection_ref",
        "vercel_integrations_review_ref",
        "termination_audit_ref",
        "observability_review_ref",
        "notification_test_ref",
        "budget_review_ref",
        "retention_days",
        "environments_isolated",
        "tls_active",
        "default_run_app_unreachable",
        "runtime_identity_roleless",
        "no_persistent_payload_storage",
        "no_payload_logging",
        "third_party_telemetry_disabled",
        "termination_leaves_no_payloads",
        "observability_controls_active",
        "notification_tests_passed",
        "budget_controls_active",
    }
)
SECURITY_FIELDS = frozenset(
    {
        "security_review_ref",
        "deployed_artifact_scan_ref",
        "repository_security_review_ref",
        "repository_control_ref",
        "product_triage_ref",
        "critical_vulnerability_count",
        "high_vulnerability_count",
        "severity_1_defect_count",
        "severity_2_defect_count",
    }
)
SIGNOFF_FIELDS = frozenset(
    {
        "product_signoff_ref",
        "nail_tech_signoff_ref",
        "privacy_security_signoff_ref",
        "engineering_signoff_ref",
    }
)


def build_release_readiness_report(evidence_directory: Path) -> dict[str, Any]:
    evidence = _load_evidence_directory(evidence_directory)
    attestations = evidence["release-attestations.json"]
    _validate_attestations(attestations)

    release_version = attestations["release_version"]
    repository = attestations["repository"]
    commit_sha = attestations["git_commit_sha"]
    controls = attestations["production_controls"]
    security = attestations["security_and_defects"]
    signoffs = attestations["signoffs"]

    model = evidence["model-release-manifest.json"]
    environments = evidence["github-environment-audit.json"]
    staging = evidence["staging-promotion.json"]
    deployment = evidence["deployment-manifest.json"]
    benchmark = evidence["onnx-runtime-benchmark.json"]
    runtime = evidence["runtime-model-verification.json"]
    promotion = evidence["image-promotion.json"]
    vercel = evidence["vercel-deployment.json"]
    smoke = evidence["deployment-smoke.json"]
    client = evidence["client-certification.json"]
    privacy = evidence["privacy-release-boundary.json"]

    expected_schemas = {
        "model_release": (model, "nailsize-model-release@7"),
        "environment_audit": (environments, "nailsize-github-environment-audit@1"),
        "staging_promotion": (staging, "nailsize-staging-promotion@1"),
        "production_deployment": (deployment, "nailsize-deployment@3"),
        "production_benchmark": (benchmark, "nailsize-cloud-run-onnx-benchmark@1"),
        "runtime_model": (runtime, "nailsize-runtime-model-verification@1"),
        "image_promotion": (promotion, "nailsize-image-promotion@1"),
        "vercel_deployment": (vercel, "nailsize-vercel-deployment@1"),
        "production_smoke": (smoke, "nailsize-deployment-smoke@2"),
        "client_certification": (client, "nailsize-client-certification@1"),
        "privacy_boundary": (privacy, "nailsize-privacy-release-boundary@1"),
    }
    schema_checks = {
        name: report.get("schema_version") == schema
        for name, (report, schema) in expected_schemas.items()
    }

    model_version = model.get("model_version")
    model_sha256 = model.get("model_sha256")
    model_identity_valid = bool(
        isinstance(model_version, str)
        and _IDENTIFIER.fullmatch(model_version)
        and isinstance(model_sha256, str)
        and _MODEL_SHA.fullmatch(model_sha256)
    )
    source_image = promotion.get("source_image_uri")
    destination_image = promotion.get("destination_image_uri")
    image_digest = promotion.get("digest")
    source_image_digest = _image_digest(source_image)
    destination_image_digest = _image_digest(destination_image)
    image_identity_valid = (
        source_image_digest is not None
        and source_image_digest == image_digest == destination_image_digest
    )
    smoke_checks = smoke.get("checks")
    smoke_by_name = (
        {item.get("name"): item for item in smoke_checks if isinstance(item, dict)}
        if isinstance(smoke_checks, list)
        else {}
    )
    smoke_contract_valid = (
        set(smoke_by_name) == EXPECTED_SMOKE_CHECKS
        and len(smoke_by_name) == len(smoke_checks or [])
        and all(item.get("passed") is True for item in smoke_by_name.values())
    )

    frontend_url = deployment.get("frontend_url")
    api_url = deployment.get("api_url")
    frontend_host = _https_host(frontend_url)
    api_host = _https_host(api_url)
    identity_chain_consistent = all(
        (
            model_identity_valid,
            image_identity_valid,
            frontend_host is not None,
            api_host is not None,
            environments.get("repository") == repository,
            staging.get("git_commit_sha") == commit_sha,
            deployment.get("git_commit_sha") == commit_sha,
            vercel.get("git_commit_sha") == commit_sha,
            client.get("tested_commit_sha") == commit_sha,
            client.get("release_version") == release_version,
            staging.get("model_release_tag") == deployment.get("model_release_tag"),
            staging.get("model_version") == model_version,
            deployment.get("model_version") == model_version,
            benchmark.get("model_version") == model_version,
            runtime.get("model_version") == model_version,
            staging.get("model_sha256") == model_sha256,
            deployment.get("model_sha256") == model_sha256,
            benchmark.get("model_sha256") == model_sha256,
            runtime.get("model_sha256") == model_sha256,
            benchmark.get("image_uri") == destination_image,
            staging.get("staging_image_uri") == source_image,
            deployment.get("promoted_from_image_uri") == source_image,
            deployment.get("image_uri") == destination_image,
            vercel.get("frontend_url") == frontend_url,
            smoke.get("frontend_host") == frontend_host,
            smoke.get("api_host") == api_host,
            smoke.get("expected_model_version") == model_version,
        )
    )

    control_refs = [value for key, value in controls.items() if key.endswith("_ref")]
    security_refs = [value for key, value in security.items() if key.endswith("_ref")]
    signoff_refs = list(signoffs.values())
    missing_evidence = sorted(
        f"{section_name}.{field}"
        for section_name, section in (
            ("production_controls", controls),
            ("security_and_defects", security),
            ("signoffs", signoffs),
        )
        for field, value in section.items()
        if field.endswith("_ref") and not _review_ref(value)
    )
    references_complete = all(
        _review_ref(value) for value in [*control_refs, *security_refs, *signoff_refs]
    )
    production_controls_passed = controls["retention_days"] == 30 and all(
        controls[field] is True
        for field in PRODUCTION_CONTROL_FIELDS
        if field not in {"retention_days"} and not field.endswith("_ref")
    )
    security_clear = all(
        security[field] == 0 for field in SECURITY_FIELDS if field.endswith("_count")
    )

    checks = {
        "artifact_schemas_valid": all(schema_checks.values()),
        "model_release_approved": model.get("approved") is True,
        "environment_boundary_passed": environments.get("passed") is True,
        "staging_promotion_passed": staging.get("passed") is True,
        "production_deployment_recorded": deployment.get("environment") == "production",
        "production_benchmark_passed": (
            benchmark.get("environment") == "production" and benchmark.get("passed") is True
        ),
        "runtime_model_ready": runtime.get("status") == "ready",
        "image_promotion_passed": promotion.get("passed") is True,
        "vercel_production_ready": (
            vercel.get("target") == "production"
            and vercel.get("ready_state") == "READY"
            and vercel.get("ready_substate") == "PROMOTED"
        ),
        "production_smoke_passed": (
            smoke.get("environment") == "production"
            and smoke.get("passed") is True
            and smoke_contract_valid
        ),
        "client_certification_passed": (
            client.get("decision") == "client_validation_passed"
            and client.get("public_launch_may_continue") is True
            and client.get("passed") is True
        ),
        "source_privacy_boundary_passed": privacy.get("passed") is True,
        "production_controls_passed": production_controls_passed,
        "security_and_defects_clear": security_clear,
        "identity_chain_consistent": identity_chain_consistent,
        "accountable_evidence_complete": references_complete,
    }
    evidence_complete = references_complete and all(schema_checks.values())
    failed_checks = sorted(name for name, passed in checks.items() if not passed)
    passed = evidence_complete and not failed_checks
    if passed:
        decision = "release_ready"
    elif not evidence_complete:
        decision = "insufficient_evidence"
    else:
        decision = "release_blocked"

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "release_version": release_version,
        "repository": repository,
        "git_commit_sha": commit_sha,
        "model_release_tag": deployment.get("model_release_tag"),
        "model_version": model_version,
        "model_sha256": model_sha256,
        "production_image_uri": destination_image,
        "production_frontend_host": frontend_host,
        "production_api_host": api_host,
        "production_revision_ref": controls["production_revision_ref"],
        "evidence_sha256": {
            name: _sha256(evidence_directory / name) for name in sorted(REQUIRED_FILENAMES)
        },
        "schema_checks": schema_checks,
        "checks": checks,
        "missing_evidence": missing_evidence,
        "failed_checks": failed_checks,
        "evidence_complete": evidence_complete,
        "decision": decision,
        "public_launch_may_continue": passed,
        "passed": passed,
    }


def _load_evidence_directory(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_dir():
        raise ValueError("Release evidence directory does not exist")
    present = {item.name for item in path.iterdir() if item.is_file()}
    if present != REQUIRED_FILENAMES:
        missing = sorted(REQUIRED_FILENAMES - present)
        unexpected = sorted(present - REQUIRED_FILENAMES)
        raise ValueError(
            f"Release evidence files do not match contract; missing={missing}, "
            f"unexpected={unexpected}"
        )
    evidence: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_FILENAMES:
        try:
            payload = json.loads((path / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Could not read release evidence file: {name}") from error
        if not isinstance(payload, dict):
            raise ValueError(f"Release evidence file must contain an object: {name}")
        evidence[name] = payload
    return evidence


def _validate_attestations(payload: dict[str, Any]) -> None:
    expected = {
        "schema_version",
        "release_version",
        "repository",
        "git_commit_sha",
        "production_controls",
        "security_and_defects",
        "signoffs",
    }
    if set(payload) != expected or payload.get("schema_version") != ATTESTATION_SCHEMA_VERSION:
        raise ValueError("Release attestations do not match the exact schema")
    if (
        not isinstance(payload.get("release_version"), str)
        or _IDENTIFIER.fullmatch(payload["release_version"]) is None
    ):
        raise ValueError("Release version must be a bounded immutable identifier")
    repository = payload.get("repository")
    if (
        not isinstance(repository, str)
        or repository.count("/") != 1
        or any(_IDENTIFIER.fullmatch(part) is None for part in repository.split("/"))
    ):
        raise ValueError("Repository must be a bounded OWNER/REPOSITORY identifier")
    if (
        not isinstance(payload.get("git_commit_sha"), str)
        or _COMMIT_SHA.fullmatch(payload["git_commit_sha"]) is None
    ):
        raise ValueError("Git commit must be an exact lowercase 40-character SHA")
    sections = (
        ("production controls", payload.get("production_controls"), PRODUCTION_CONTROL_FIELDS),
        ("security and defects", payload.get("security_and_defects"), SECURITY_FIELDS),
        ("signoffs", payload.get("signoffs"), SIGNOFF_FIELDS),
    )
    for label, section, fields in sections:
        if not isinstance(section, dict) or set(section) != fields:
            raise ValueError(f"Release {label} do not match the exact schema")
        for key, value in section.items():
            if key.endswith("_ref") and not _optional_ref(value):
                raise ValueError(f"Release {label} references must use bounded safe identifiers")
            if key.endswith("_count") and not _nonnegative_int(value):
                raise ValueError(f"Release {label} counts must be non-negative integers")
    controls = payload["production_controls"]
    if not _nonnegative_int(controls["retention_days"]):
        raise ValueError("Log retention must be a non-negative integer number of days")
    for key, value in controls.items():
        if not key.endswith("_ref") and key != "retention_days" and not isinstance(value, bool):
            raise ValueError("Production control results must be booleans")


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _review_ref(value: Any) -> bool:
    return isinstance(value, str) and _EVIDENCE_REF.fullmatch(value) is not None


def _optional_ref(value: Any) -> bool:
    return value == "" or _review_ref(value)


def _image_digest(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = _DIGEST_IMAGE.fullmatch(value)
    return f"sha256:{match.group('digest')}" if match else None


def _https_host(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return None
    return parsed.hostname


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a fail-closed aggregate production release-readiness report"
    )
    parser.add_argument("evidence_directory", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        report = build_release_readiness_report(arguments.evidence_directory)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
