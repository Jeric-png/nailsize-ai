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
    "sqlalchemy",
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


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


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


def test_runtime_image_copies_only_the_production_package() -> None:
    dockerfile = (INFERENCE_ROOT / "Dockerfile").read_text(encoding="utf-8")
    copy_lines = [
        line.strip()
        for line in dockerfile.splitlines()
        if line.lstrip().upper().startswith("COPY ")
    ]

    assert copy_lines == ["COPY pyproject.toml ./", "COPY app ./app"]
    assert "COPY ." not in dockerfile


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
