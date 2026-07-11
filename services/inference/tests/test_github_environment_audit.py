import importlib.util
import json
import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPOSITORY_ROOT / "services/inference/scripts/audit_github_environments.py"
SPEC = importlib.util.spec_from_file_location("audit_github_environments", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class FakeClient:
    repository = "Jeric-png/nailsize-ai"

    def __init__(self, responses: dict[str, dict[str, object]]) -> None:
        self.responses = responses

    def get_json(self, suffix: str) -> dict[str, object]:
        return self.responses[suffix]


def named_page(key: str, names: set[str]) -> dict[str, object]:
    return {"total_count": len(names), key: [{"name": name} for name in sorted(names)]}


def protected_environment(name: str) -> dict[str, object]:
    return {
        "name": name,
        "protection_rules": [
            {
                "type": "required_reviewers",
                "prevent_self_review": name == "production",
                "reviewers": [{"type": "User", "reviewer": {"login": "private-reviewer"}}],
            },
            {"type": "branch_policy"},
        ],
        "deployment_branch_policy": {
            "protected_branches": False,
            "custom_branch_policies": True,
        },
    }


def valid_responses() -> dict[str, dict[str, object]]:
    environments = [
        {"name": "development", "protection_rules": [], "deployment_branch_policy": None},
        protected_environment("staging"),
        protected_environment("production"),
    ]
    responses: dict[str, dict[str, object]] = {
        "/environments?per_page=100": {
            "total_count": len(environments),
            "environments": environments,
        }
    }
    responses["/development/variables?per_page=100"] = named_page("variables", set())
    responses["/development/secrets?per_page=100"] = named_page("secrets", set())
    for name in AUDIT.DEPLOYMENT_ENVIRONMENTS:
        responses[f"/{name}/variables?per_page=100"] = named_page(
            "variables", set(AUDIT.REQUIRED_VARIABLE_NAMES)
        )
        responses[f"/{name}/secrets?per_page=100"] = named_page(
            "secrets", set(AUDIT.REQUIRED_SECRET_NAMES)
        )
        responses[f"/{name}/deployment-branch-policies?per_page=100"] = named_page(
            "branch_policies", {"main"}
        )
    return responses


def test_environment_audit_passes_without_copying_secret_values_or_reviewer_names() -> None:
    report = AUDIT.audit_github_environments(FakeClient(valid_responses()))

    assert report["passed"] is True
    serialized = json.dumps(report)
    assert "private-reviewer" not in serialized
    assert "secret_value" not in serialized
    assert [environment["name"] for environment in report["environments"]] == list(
        AUDIT.EXPECTED_ENVIRONMENTS
    )


def test_environment_audit_fails_closed_for_missing_or_shadow_environments() -> None:
    responses = {
        "/environments?per_page=100": {
            "total_count": 1,
            "environments": [{"name": "unreviewed-preview"}],
        }
    }

    report = AUDIT.audit_github_environments(FakeClient(responses))

    assert report["passed"] is False
    assert report["unexpected_environment_names"] == ["unreviewed-preview"]
    assert report["environments"][1] == {
        "name": "staging",
        "exists": False,
        "passed": False,
    }


def test_environment_audit_rejects_configuration_and_protection_drift() -> None:
    responses = valid_responses()
    responses["/staging/variables?per_page=100"] = named_page(
        "variables", set(AUDIT.REQUIRED_VARIABLE_NAMES) - {"API_DOMAIN"} | {"UNREVIEWED_VALUE"}
    )
    responses["/production/deployment-branch-policies?per_page=100"] = named_page(
        "branch_policies", {"release-candidate"}
    )
    production = responses["/environments?per_page=100"]["environments"][2]
    production["protection_rules"][0]["prevent_self_review"] = False

    report = AUDIT.audit_github_environments(FakeClient(responses))

    staging, production = report["environments"][1:]
    assert report["passed"] is False
    assert staging["missing_variable_names"] == ["API_DOMAIN"]
    assert staging["unexpected_variable_names"] == ["UNREVIEWED_VALUE"]
    assert production["deployment_branch_names"] == ["release-candidate"]
    assert production["prevent_self_review"] is False


def test_environment_audit_rejects_unrestricted_deployment_and_development_secrets() -> None:
    responses = valid_responses()
    responses["/development/secrets?per_page=100"] = named_page("secrets", {"SHADOW_TOKEN"})
    staging = responses["/environments?per_page=100"]["environments"][1]
    staging["deployment_branch_policy"] = None
    del responses["/staging/deployment-branch-policies?per_page=100"]

    report = AUDIT.audit_github_environments(FakeClient(responses))

    development, staging = report["environments"][:2]
    assert report["passed"] is False
    assert development["configured_secret_names"] == ["SHADOW_TOKEN"]
    assert development["passed"] is False
    assert staging["deployment_branch_names"] == []
    assert staging["passed"] is False


def test_audit_contract_matches_workflow_and_deployment_documentation() -> None:
    workflow = (REPOSITORY_ROOT / ".github/workflows/deploy.yml").read_text()
    documentation = (REPOSITORY_ROOT / "docs/deployment.md").read_text()
    workflow_variables = set(re.findall(r"\$\{\{ vars\.([A-Z0-9_]+) \}\}", workflow))
    workflow_secrets = set(re.findall(r"\$\{\{ secrets\.([A-Z0-9_]+) \}\}", workflow))

    assert workflow_variables == set(AUDIT.REQUIRED_VARIABLE_NAMES)
    assert workflow_secrets == set(AUDIT.REQUIRED_SECRET_NAMES)
    for name in AUDIT.REQUIRED_VARIABLE_NAMES:
        assert f"\n{name}\n" in documentation
    for name in AUDIT.REQUIRED_SECRET_NAMES:
        assert f"`{name}`" in documentation
