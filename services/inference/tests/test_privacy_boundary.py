import ast
import re
import tomllib
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
INFERENCE_ROOT = REPOSITORY_ROOT / "services" / "inference"

FORBIDDEN_RUNTIME_IMPORTS = {
    "boto3",
    "google.cloud.storage",
    "nailsize_ml",
    "sentry_sdk",
    "shelve",
    "sqlite3",
    "sqlalchemy",
    "tempfile",
    "torch",
    "torchvision",
}
FORBIDDEN_DEPENDENCY_FRAGMENTS = {
    "boto3",
    "google-cloud-storage",
    "sentry-sdk",
    "sqlalchemy",
    "torch",
    "torchvision",
}
FORBIDDEN_FILESYSTEM_METHODS = {
    "hardlink_to",
    "mkdir",
    "rename",
    "replace",
    "symlink_to",
    "touch",
    "write_bytes",
    "write_text",
}
FORBIDDEN_BROWSER_PERSISTENCE = {
    "caches.open",
    "indexedDB",
    "localStorage",
    "navigator.sendBeacon",
    "navigator.storage",
    "sessionStorage",
}


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _filesystem_write_lines(path: Path) -> list[int]:
    writes: list[int] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_FILESYSTEM_METHODS:
            writes.append(node.lineno)
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "open":
            continue
        mode_node = next(
            (keyword.value for keyword in node.keywords if keyword.arg == "mode"),
            node.args[1] if len(node.args) > 1 else ast.Constant("r"),
        )
        if not isinstance(mode_node, ast.Constant) or not isinstance(mode_node.value, str):
            writes.append(node.lineno)
        elif any(flag in mode_node.value for flag in "wax+"):
            writes.append(node.lineno)
    return writes


def test_production_runtime_cannot_import_training_or_persistence_clients() -> None:
    imported = {
        module
        for source in (INFERENCE_ROOT / "app").glob("*.py")
        for module in _imported_modules(source)
    }

    violations = {
        forbidden
        for forbidden in FORBIDDEN_RUNTIME_IMPORTS
        if any(module == forbidden or module.startswith(f"{forbidden}.") for module in imported)
    }
    assert not violations, f"Forbidden production imports: {sorted(violations)}"


def test_production_package_has_no_training_or_persistence_dependencies() -> None:
    configuration = tomllib.loads((INFERENCE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = {
        re.split(r"[<>=!~\[]", dependency, maxsplit=1)[0].lower()
        for dependency in configuration["project"]["dependencies"]
    }

    assert dependencies.isdisjoint(FORBIDDEN_DEPENDENCY_FRAGMENTS)


def test_production_runtime_has_no_filesystem_write_path() -> None:
    violations: dict[str, list[int]] = {}
    for source in (INFERENCE_ROOT / "app").glob("*.py"):
        lines = _filesystem_write_lines(source)
        if lines:
            violations[str(source.relative_to(REPOSITORY_ROOT))] = lines

    assert not violations, f"Production filesystem writes: {violations}"


def test_multipart_uploads_are_bounded_below_the_disk_rollover_threshold() -> None:
    source = (INFERENCE_ROOT / "app" / "main.py").read_text(encoding="utf-8")

    assert "configure_in_memory_multipart(settings.max_encoded_bytes)" in source
    assert "InMemoryRequestLimitMiddleware" in source


def test_browser_has_no_persistent_storage_or_payload_export_path() -> None:
    sources = "\n".join(
        source.read_text(encoding="utf-8")
        for source in (REPOSITORY_ROOT / "apps" / "web" / "src").rglob("*")
        if source.suffix in {".ts", ".tsx"}
    )

    violations = {token for token in FORBIDDEN_BROWSER_PERSISTENCE if token in sources}
    assert not violations, f"Forbidden browser persistence APIs: {sorted(violations)}"


def test_runtime_image_copies_only_the_production_package() -> None:
    dockerfile = (INFERENCE_ROOT / "Dockerfile").read_text(encoding="utf-8")
    copy_lines = [
        line.strip()
        for line in dockerfile.splitlines()
        if line.lstrip().upper().startswith("COPY ")
    ]

    assert copy_lines == [
        "COPY pyproject.toml ./",
        "COPY app ./app",
        "COPY models/hand_landmarker.task ./models/hand_landmarker.task",
        "COPY models/nail-segmentation.onnx ./models/nail-segmentation.onnx",
    ]
    assert "COPY ." not in dockerfile
    assert "pip install '.[landmarks]'" in dockerfile


def test_training_tooling_is_manual_and_has_no_production_data_ingress() -> None:
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "model-tooling.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in workflow
    for forbidden in (
        "schedule:",
        "workflow_run:",
        "download-artifact",
        "google-github-actions/auth",
    ):
        assert forbidden not in workflow


def test_ci_emits_the_source_managed_privacy_release_report() -> None:
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "verify_privacy_release_boundary.py" in workflow
    assert "privacy-release-boundary.json" in workflow
    assert "name: privacy-release-boundary" in workflow
