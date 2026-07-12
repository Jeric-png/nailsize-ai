import argparse
import json
import re
import tomllib
from pathlib import Path

SCHEMA_VERSION = "nailsize-privacy-release-boundary@1"

ALLOWED_WEB_RUNTIME_DEPENDENCIES = {
    "@nailsize/contracts",
    "react",
    "react-dom",
    "react-router-dom",
}
ALLOWED_INFERENCE_RUNTIME_DEPENDENCIES = {
    "fastapi",
    "httpx",
    "numpy",
    "onnxruntime",
    "opencv-python-headless",
    "pillow",
    "pillow-heif",
    "pydantic-settings",
    "python-multipart",
    "starlette",
    "uvicorn",
}
ALLOWED_TERRAFORM_RESOURCE_ADDRESSES = {
    "google_artifact_registry_repository.inference",
    "google_billing_budget.project",
    "google_cloud_run_v2_job.onnx_benchmark",
    "google_cloud_run_v2_service.inference",
    "google_cloud_run_v2_service_iam_member.public_invoker",
    "google_compute_backend_service.inference",
    "google_compute_global_address.api",
    "google_compute_global_forwarding_rule.http_redirect",
    "google_compute_global_forwarding_rule.https",
    "google_compute_managed_ssl_certificate.api",
    "google_compute_region_network_endpoint_group.inference",
    "google_compute_security_policy.edge",
    "google_compute_target_http_proxy.http_redirect",
    "google_compute_target_https_proxy.api",
    "google_compute_url_map.api",
    "google_compute_url_map.http_redirect",
    "google_logging_metric.cold_starts",
    "google_logging_metric.malformed_uploads",
    "google_logging_metric.measurement_events",
    "google_logging_metric.stage_latency",
    "google_logging_project_bucket_config.default",
    "google_monitoring_alert_policy.error_rate",
    "google_monitoring_alert_policy.instance_saturation",
    "google_monitoring_alert_policy.malformed_upload_spike",
    "google_monitoring_alert_policy.p95_latency",
    "google_monitoring_dashboard.service",
    "google_project_service.required",
    "google_service_account.runtime",
}
ALLOWED_TERRAFORM_LOG_FIELDS = {
    "chart_version",
    "cold_start",
    "duration_ms",
    "error_code",
    "event",
    "model_version",
    "stage",
    "status_code",
}

_DEPENDENCY_NAME = re.compile(r"^[A-Za-z0-9_.-]+")
_TERRAFORM_RESOURCE = re.compile(r'^\s*resource\s+"([^"]+)"\s+"([^"]+)"\s*{', re.MULTILINE)
_TERRAFORM_LOG_FIELD = re.compile(r"jsonPayload\.([A-Za-z0-9_]+)")
_LOAD_BALANCER_LOGGING = re.compile(
    r"log_config\s*{\s*enable\s*=\s*true\s*sample_rate\s*=\s*1(?:\.0)?\s*}",
    re.MULTILINE,
)


def verify_privacy_release_boundary(repository_root: Path) -> dict[str, object]:
    root = repository_root.resolve()
    web_dependencies = _web_runtime_dependencies(root / "apps/web/package.json")
    inference_dependencies = _inference_runtime_dependencies(
        root / "services/inference/pyproject.toml"
    )
    terraform_resources, terraform_log_fields = _terraform_resources(root / "infra")
    terraform_resource_types = {
        address.split(".", maxsplit=1)[0] for address in terraform_resources
    }

    _require_exact_set(
        "Web runtime dependencies", web_dependencies, ALLOWED_WEB_RUNTIME_DEPENDENCIES
    )
    _require_exact_set(
        "Inference runtime dependencies",
        inference_dependencies,
        ALLOWED_INFERENCE_RUNTIME_DEPENDENCIES,
    )
    _require_exact_set(
        "Terraform resource addresses",
        terraform_resources,
        ALLOWED_TERRAFORM_RESOURCE_ADDRESSES,
    )
    _require_subset("Terraform log fields", terraform_log_fields, ALLOWED_TERRAFORM_LOG_FIELDS)
    _verify_container_logging(root / "services/inference/Dockerfile")
    _verify_platform_logging(root / "infra/platform/main.tf")
    _verify_browser_transport(root / "apps/web/src/api.ts")
    _verify_browser_policy(root / "vercel.json")

    return {
        "schema_version": SCHEMA_VERSION,
        "scope": "source-managed-runtime-and-infrastructure",
        "web_runtime_dependency_count": len(web_dependencies),
        "inference_runtime_dependency_count": len(inference_dependencies),
        "terraform_resource_count": len(terraform_resources),
        "terraform_resource_type_count": len(terraform_resource_types),
        "terraform_log_field_count": len(terraform_log_fields),
        "container_access_log_disabled": True,
        "load_balancer_metadata_logging_only": True,
        "browser_payload_url_fields": 0,
        "third_party_browser_script_origins": 0,
        "persistent_payload_service_types": 0,
        "passed": True,
    }


def _web_runtime_dependencies(path: Path) -> set[str]:
    package = json.loads(path.read_text(encoding="utf-8"))
    dependencies = package.get("dependencies")
    if not isinstance(dependencies, dict) or not all(
        isinstance(name, str) and isinstance(version, str) for name, version in dependencies.items()
    ):
        raise ValueError("Web runtime dependencies must be a string map")
    return set(dependencies)


def _inference_runtime_dependencies(path: Path) -> set[str]:
    configuration = tomllib.loads(path.read_text(encoding="utf-8"))
    dependencies = configuration.get("project", {}).get("dependencies")
    if not isinstance(dependencies, list) or not all(
        isinstance(dependency, str) for dependency in dependencies
    ):
        raise ValueError("Inference runtime dependencies must be a string list")

    names: set[str] = set()
    for dependency in dependencies:
        match = _DEPENDENCY_NAME.match(dependency)
        if match is None:
            raise ValueError("Inference runtime dependency has an invalid name")
        names.add(match.group(0).lower())
    return names


def _terraform_resources(infra_root: Path) -> tuple[set[str], set[str]]:
    sources = [path.read_text(encoding="utf-8") for path in infra_root.rglob("*.tf")]
    resources = {
        f"{resource_type}.{resource_name}"
        for source in sources
        for resource_type, resource_name in _TERRAFORM_RESOURCE.findall(source)
    }
    if not resources:
        raise ValueError("No Terraform resources were found")
    log_fields = {field for source in sources for field in _TERRAFORM_LOG_FIELD.findall(source)}
    return resources, log_fields


def _require_exact_set(label: str, actual: set[str], allowed: set[str]) -> None:
    if actual != allowed:
        added = sorted(actual - allowed)
        missing = sorted(allowed - actual)
        raise ValueError(f"{label} changed; added={added}, missing={missing}")


def _require_subset(label: str, actual: set[str], allowed: set[str]) -> None:
    unexpected = sorted(actual - allowed)
    if unexpected:
        raise ValueError(f"{label} require privacy review: {unexpected}")


def _verify_container_logging(path: Path) -> None:
    dockerfile = path.read_text(encoding="utf-8")
    if "MPLCONFIGDIR=/tmp/matplotlib" not in dockerfile:
        raise ValueError("Third-party runtime caches must be confined to ephemeral /tmp")
    command_lines = [
        line.removeprefix("CMD ") for line in dockerfile.splitlines() if line.startswith("CMD ")
    ]
    if len(command_lines) != 1:
        raise ValueError("Runtime image must define exactly one JSON-form CMD")
    try:
        command = json.loads(command_lines[0])
    except json.JSONDecodeError as error:
        raise ValueError("Runtime CMD must use JSON form") from error
    if not isinstance(command, list) or "--no-access-log" not in command:
        raise ValueError("Runtime access logging must be disabled")


def _verify_platform_logging(path: Path) -> None:
    configuration = path.read_text(encoding="utf-8")
    if "optional_fields" in configuration or "optional_mode" in configuration:
        raise ValueError("Optional load balancer log fields are prohibited")
    if len(_LOAD_BALANCER_LOGGING.findall(configuration)) != 1:
        raise ValueError("Load balancer must use one complete native metadata log configuration")
    if "strip_query            = true" not in configuration:
        raise ValueError("HTTP redirects must discard query strings")


def _verify_browser_transport(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    required = "fetch(`${apiUrl}/v1/measure`, {"
    if source.count(required) != 1:
        raise ValueError("Browser must send payloads to one fixed query-free measurement path")
    if "URLSearchParams" in source or "?${" in source:
        raise ValueError("Browser measurement transport must not place data in URL fields")


def _verify_browser_policy(path: Path) -> None:
    configuration = json.loads(path.read_text(encoding="utf-8"))
    header_values = {
        header.get("key"): header.get("value")
        for rule in configuration.get("headers", [])
        for header in rule.get("headers", [])
        if isinstance(header, dict)
    }
    policy = header_values.get("Content-Security-Policy")
    directives = set(policy.split("; ")) if isinstance(policy, str) else set()
    if "script-src 'self'" not in directives:
        raise ValueError("Browser policy must prohibit third-party script origins")
    if "report-uri" in policy or "report-to" in policy:
        raise ValueError("Browser policy must not export violation payloads")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit the source-managed privacy boundary before a release"
    )
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        report = verify_privacy_release_boundary(arguments.repository_root)
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        parser.error(str(error))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
