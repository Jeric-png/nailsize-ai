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


def test_ci_scans_the_built_image_before_privacy_smoke() -> None:
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    container_job = workflow.split("  container:", 1)[1]

    image_build = container_job.index("docker build -t nailsize-inference:contract .")
    image_scan = container_job.index("- name: Scan the built runtime image")
    privacy_smoke = container_job.index("- name: Privacy-smoke the scanned runtime image")

    assert image_build < image_scan < privacy_smoke
    scan_step = container_job[image_scan:privacy_smoke]
    assert "scan-type: image" in scan_step
    assert "image-ref: nailsize-inference:contract" in scan_step
    assert "vuln-type: os,library" in scan_step
    assert "severity: HIGH,CRITICAL" in scan_step
    assert 'exit-code: "1"' in scan_step
    assert "ignore-unfixed: false" in scan_step
    assert "ignore-unfixed: true" not in workflow
