import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ACTION_REFERENCE = re.compile(r"uses:\s+([^@\s]+)@([^\s#]+)")
COMMIT_SHA = re.compile(r"[0-9a-f]{40}")


def test_external_github_actions_are_immutable_commit_pinned() -> None:
    mutable_references: list[str] = []

    for workflow_path in sorted((REPOSITORY_ROOT / ".github" / "workflows").glob("*.yml")):
        for action, reference in ACTION_REFERENCE.findall(workflow_path.read_text()):
            if action.startswith("./"):
                continue
            if COMMIT_SHA.fullmatch(reference) is None:
                mutable_references.append(f"{workflow_path.name}: {action}@{reference}")

    assert mutable_references == []


def test_dependabot_covers_every_dependency_manifest_family() -> None:
    config = (REPOSITORY_ROOT / ".github" / "dependabot.yml").read_text()

    required_ecosystems = {"npm", "pip", "github-actions", "docker", "terraform"}
    configured_ecosystems = set(re.findall(r"package-ecosystem:\s+([\w-]+)", config))
    assert configured_ecosystems == required_ecosystems

    for directory in (
        "/services/inference",
        "/ml",
        "/infra/bootstrap",
        "/infra/observability",
        "/infra/platform",
    ):
        assert directory in config

    assert config.count("interval: weekly") == len(required_ecosystems)


def test_dependabot_suppresses_unsupported_major_version_noise() -> None:
    config = (REPOSITORY_ROOT / ".github" / "dependabot.yml").read_text()

    # GitHub documents these ignores as applying to version updates only;
    # vulnerability-driven security updates remain enabled independently.
    assert config.count("- version-update:semver-major") == 4
    assert "dependency-name: eslint-plugin-react-refresh" in config
    assert "- version-update:semver-minor" in config
    assert "dependency-name: python" in config
    assert '- ">= 3.13"' in config
