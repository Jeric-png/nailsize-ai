import json
import shutil
from pathlib import Path

import pytest

from scripts.verify_privacy_release_boundary import (
    SCHEMA_VERSION,
    verify_privacy_release_boundary,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _copy_audit_surface(destination: Path) -> Path:
    for relative in (
        "apps/web/package.json",
        "apps/web/src/api.ts",
        "services/inference/pyproject.toml",
        "services/inference/Dockerfile",
        "vercel.json",
    ):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPOSITORY_ROOT / relative, target)
    shutil.copytree(REPOSITORY_ROOT / "infra", destination / "infra")
    return destination


def test_current_repository_passes_source_managed_privacy_audit() -> None:
    report = verify_privacy_release_boundary(REPOSITORY_ROOT)

    assert report == {
        "schema_version": SCHEMA_VERSION,
        "scope": "source-managed-runtime-and-infrastructure",
        "web_runtime_dependency_count": 4,
        "inference_runtime_dependency_count": 11,
        "terraform_resource_count": 28,
        "terraform_resource_type_count": 20,
        "terraform_log_field_count": 8,
        "container_access_log_disabled": True,
        "load_balancer_metadata_logging_only": True,
        "browser_payload_url_fields": 0,
        "third_party_browser_script_origins": 0,
        "persistent_payload_service_types": 0,
        "passed": True,
    }


def test_rejects_unreviewed_browser_runtime_dependency(tmp_path: Path) -> None:
    root = _copy_audit_surface(tmp_path)
    manifest_path = root / "apps/web/package.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["dependencies"]["@sentry/react"] = "latest"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="Web runtime dependencies changed"):
        verify_privacy_release_boundary(root)


def test_rejects_persistent_infrastructure_service(tmp_path: Path) -> None:
    root = _copy_audit_surface(tmp_path)
    (root / "infra/platform/payloads.tf").write_text(
        'resource "google_storage_bucket" "payloads" { name = "payloads" }\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="resource addresses changed.*google_storage_bucket"):
        verify_privacy_release_boundary(root)


def test_rejects_new_instance_of_an_allowlisted_resource_type(tmp_path: Path) -> None:
    root = _copy_audit_surface(tmp_path)
    (root / "infra/observability/payload_metric.tf").write_text(
        'resource "google_logging_metric" "payload_widths" { name = "payload-widths" }\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="resource addresses changed.*payload_widths"):
        verify_privacy_release_boundary(root)


def test_rejects_unreviewed_structured_log_field(tmp_path: Path) -> None:
    root = _copy_audit_surface(tmp_path)
    observability = root / "infra/observability/main.tf"
    observability.write_text(
        observability.read_text(encoding="utf-8").replace(
            "jsonPayload.duration_ms)", "jsonPayload.width_mm)"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Terraform log fields.*width_mm"):
        verify_privacy_release_boundary(root)


def test_rejects_runtime_access_logs(tmp_path: Path) -> None:
    root = _copy_audit_surface(tmp_path)
    dockerfile = root / "services/inference/Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text(encoding="utf-8").replace(', "--no-access-log"', ""),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="access logging must be disabled"):
        verify_privacy_release_boundary(root)


def test_rejects_runtime_cache_outside_ephemeral_tmp(tmp_path: Path) -> None:
    root = _copy_audit_surface(tmp_path)
    dockerfile = root / "services/inference/Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text(encoding="utf-8").replace(
            "MPLCONFIGDIR=/tmp/matplotlib", "MPLCONFIGDIR=/home/appuser/.config"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="confined to ephemeral /tmp"):
        verify_privacy_release_boundary(root)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("strip_query            = true", "strip_query            = false", "discard query"),
        (
            "sample_rate = 1",
            'sample_rate = 1\n    optional_fields = ["tls.protocol"]',
            "Optional load balancer log fields",
        ),
    ],
)
def test_rejects_payload_bearing_edge_logging(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    root = _copy_audit_surface(tmp_path)
    platform = root / "infra/platform/main.tf"
    platform.write_text(platform.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        verify_privacy_release_boundary(root)


def test_rejects_measurement_data_in_url_fields(tmp_path: Path) -> None:
    root = _copy_audit_surface(tmp_path)
    api = root / "apps/web/src/api.ts"
    api.write_text(
        api.read_text(encoding="utf-8").replace(
            "`${apiUrl}/v1/measure`", "`${apiUrl}/v1/measure?capture=${captureType}`"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="query-free measurement path"):
        verify_privacy_release_boundary(root)


def test_rejects_third_party_browser_scripts(tmp_path: Path) -> None:
    root = _copy_audit_surface(tmp_path)
    vercel = root / "vercel.json"
    vercel.write_text(
        vercel.read_text(encoding="utf-8").replace(
            "script-src 'self'", "script-src 'self' https://telemetry.example"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="third-party script origins"):
        verify_privacy_release_boundary(root)
