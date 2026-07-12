import importlib.util
import json
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPOSITORY_ROOT / "services/inference/scripts/audit_vercel_projects.py"
SPEC = importlib.util.spec_from_file_location("audit_vercel_projects", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

TEAM_ID = "team_nailsize"
PROJECT_ID = "prj_nailsize"
PROJECT_NAME = "nailsize-ai-staging"
REPOSITORY = "Jeric-png/nailsize-ai"
REPOSITORY_ID = "1297575199"


class FakeClient:
    team_id = TEAM_ID

    def __init__(self, responses):
        self.responses = responses

    def get_json(self, path, query):
        return self.responses[(path, tuple(sorted(query.items())))]


def _project():
    return {
        "id": PROJECT_ID,
        "name": PROJECT_NAME,
        "accountId": TEAM_ID,
        "framework": "vite",
        "buildCommand": "npm run build",
        "installCommand": "npm ci",
        "outputDirectory": "apps/web/dist",
        "rootDirectory": None,
        "nodeVersion": "22.x",
        "directoryListing": False,
        "autoExposeSystemEnvs": False,
        "protectedSourcemaps": True,
        "features": {"webAnalytics": False},
        "link": {
            "type": "github",
            "org": "Jeric-png",
            "repo": "nailsize-ai",
            "repoId": int(REPOSITORY_ID),
            "productionBranch": "main",
            "deployHooks": [],
            "gitCredentialId": "private-git-credential",
        },
    }


def _responses(environment_variables=None, integrations=None):
    return {
        (f"/v9/projects/{PROJECT_ID}", ()): _project(),
        (
            "/v1/integrations/configurations",
            (("projectId", PROJECT_ID), ("view", "project")),
        ): [] if integrations is None else integrations,
        (f"/v10/projects/{PROJECT_ID}/env", ()): {
            "envs": [] if environment_variables is None else environment_variables
        },
    }


def _audit(responses):
    return AUDIT.audit_vercel_projects(
        FakeClient(responses),
        (AUDIT.ProjectExpectation(PROJECT_ID, PROJECT_NAME),),
        REPOSITORY,
        REPOSITORY_ID,
    )


def test_audit_accepts_private_static_project_without_copying_sensitive_metadata() -> None:
    report = _audit(_responses())

    assert report["passed"] is True
    assert report["projects"] == [
        {
            "project_id": PROJECT_ID,
            "project_name": PROJECT_NAME,
            "release_settings_match": True,
            "git_settings_match": True,
            "privacy_settings_match": True,
            "web_analytics_enabled": False,
            "integration_count": 0,
            "configured_environment_variable_names": [],
            "passed": True,
        }
    ]
    serialized = json.dumps(report)
    assert "private-git-credential" not in serialized
    assert "VERCEL_TOKEN" not in serialized


def test_audit_accepts_only_release_bound_public_api_origin_metadata() -> None:
    report = _audit(
        _responses(
            environment_variables=[
                {
                    "key": "VITE_INFERENCE_API_URL",
                    "value": "encrypted-or-omitted-by-vercel",
                    "type": "plain",
                    "target": ["production"],
                    "gitBranch": None,
                    "configurationId": None,
                    "edgeConfigId": None,
                }
            ]
        )
    )

    assert report["passed"] is True
    assert report["projects"][0]["configured_environment_variable_names"] == [
        "VITE_INFERENCE_API_URL"
    ]
    assert "encrypted-or-omitted-by-vercel" not in json.dumps(report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("nodeVersion", "24.x"),
        ("directoryListing", True),
        ("autoExposeSystemEnvs", True),
        ("protectedSourcemaps", False),
        ("features", {"webAnalytics": True}),
    ],
)
def test_audit_fails_closed_for_release_or_privacy_setting_drift(field, value) -> None:
    responses = _responses()
    responses[(f"/v9/projects/{PROJECT_ID}", ())][field] = value

    report = _audit(responses)

    assert report["passed"] is False


def test_audit_rejects_integrations_hooks_and_unreviewed_environment_variables() -> None:
    responses = _responses(
        environment_variables=[
            {
                "key": "SESSION_REPLAY_TOKEN",
                "type": "sensitive",
                "target": ["production"],
            }
        ],
        integrations=[{"id": "private-integration-id", "slug": "session-replay"}],
    )
    responses[(f"/v9/projects/{PROJECT_ID}", ())]["link"]["deployHooks"] = [
        {"url": "https://private-hook.example"}
    ]

    report = _audit(responses)

    project = report["projects"][0]
    assert report["passed"] is False
    assert project["integration_count"] == 1
    assert project["configured_environment_variable_names"] == ["SESSION_REPLAY_TOKEN"]
    serialized = json.dumps(report)
    assert "private-integration-id" not in serialized
    assert "private-hook.example" not in serialized


def test_audit_rejects_duplicate_projects_and_malformed_response_shapes() -> None:
    expectation = AUDIT.ProjectExpectation(PROJECT_ID, PROJECT_NAME)
    with pytest.raises(ValueError, match="IDs must be unique"):
        AUDIT.audit_vercel_projects(
            FakeClient(_responses()),
            (expectation, expectation),
            REPOSITORY,
            REPOSITORY_ID,
        )

    responses = _responses()
    responses[(f"/v10/projects/{PROJECT_ID}/env", ())] = {"envs": "not-a-list"}
    with pytest.raises(ValueError, match="object list"):
        _audit(responses)
