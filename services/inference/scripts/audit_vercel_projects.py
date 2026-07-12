"""Audit privacy and release controls on Vercel frontend projects."""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

SCHEMA_VERSION = "nailsize-vercel-project-audit@1"
ALLOWED_ENVIRONMENT_VARIABLES = frozenset({"VITE_INFERENCE_API_URL"})
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_PROJECT_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,99}")
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_MAX_RESPONSE_BYTES = 1_000_000


@dataclass(frozen=True)
class ProjectExpectation:
    project_id: str
    project_name: str


class ProjectClient(Protocol):
    team_id: str

    def get_json(self, path: str, query: dict[str, str]) -> object: ...


class VercelProjectClient:
    def __init__(self, team_id: str, token: str) -> None:
        if _IDENTIFIER.fullmatch(team_id) is None:
            raise ValueError("Vercel team ID is invalid")
        if not token.strip():
            raise ValueError("VERCEL_TOKEN is required")
        self.team_id = team_id
        self._token = token

    def get_json(self, path: str, query: dict[str, str]) -> object:
        if not path.startswith("/") or "//" in path:
            raise ValueError("Vercel API path must be an absolute path")
        parameters = {"teamId": self.team_id, **query}
        url = f"https://api.vercel.com{path}?{urlencode(parameters)}"
        request = Request(  # noqa: S310 - URL is restricted to the fixed Vercel host.
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "nailsize-vercel-project-audit",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed HTTPS host.
                payload = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            raise RuntimeError(f"Vercel API returned HTTP {error.code} for {path}") from None
        except URLError as error:
            raise RuntimeError(
                "Vercel API request failed before a response was received"
            ) from error
        if len(payload) > _MAX_RESPONSE_BYTES:
            raise ValueError("Vercel API response exceeded the audit size limit")
        return json.loads(payload)


def audit_vercel_projects(
    client: ProjectClient,
    expectations: tuple[ProjectExpectation, ...],
    github_repository: str,
    github_repository_id: str,
) -> dict[str, object]:
    if not expectations:
        raise ValueError("At least one Vercel project is required")
    if len({item.project_id for item in expectations}) != len(expectations):
        raise ValueError("Vercel project IDs must be unique")
    if len({item.project_name for item in expectations}) != len(expectations):
        raise ValueError("Vercel project names must be unique")
    if _REPOSITORY.fullmatch(github_repository) is None:
        raise ValueError("GitHub repository must use OWNER/REPOSITORY form")
    if not github_repository_id.isdigit():
        raise ValueError("GitHub repository ID must be numeric")

    projects = [
        _audit_project(client, item, github_repository, github_repository_id)
        for item in expectations
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "team_id": client.team_id,
        "github_repository": github_repository,
        "github_repository_id": github_repository_id,
        "projects": projects,
        "passed": all(project["passed"] for project in projects),
    }


def _audit_project(
    client: ProjectClient,
    expectation: ProjectExpectation,
    github_repository: str,
    github_repository_id: str,
) -> dict[str, object]:
    if _IDENTIFIER.fullmatch(expectation.project_id) is None:
        raise ValueError("Vercel project ID is invalid")
    if _PROJECT_NAME.fullmatch(expectation.project_name) is None:
        raise ValueError("Vercel project name is invalid")
    encoded_id = quote(expectation.project_id, safe="")
    project = _object(client.get_json(f"/v9/projects/{encoded_id}", {}), "project")
    integrations = _object_list(
        client.get_json(
            "/v1/integrations/configurations",
            {"view": "project", "projectId": expectation.project_id},
        ),
        "integrations",
    )
    environment_page = _object(
        client.get_json(f"/v10/projects/{encoded_id}/env", {}), "environment page"
    )
    environment_variables = _object_list(environment_page.get("envs"), "environment variables")
    environment_names = _environment_names(environment_variables)

    owner, repository = github_repository.split("/", 1)
    link = project.get("link")
    features = project.get("features")
    release_settings_match = (
        project.get("id") == expectation.project_id
        and project.get("name") == expectation.project_name
        and project.get("accountId") == client.team_id
        and project.get("framework") == "vite"
        and project.get("buildCommand") == "npm run build"
        and project.get("installCommand") == "npm ci"
        and project.get("outputDirectory") == "apps/web/dist"
        and project.get("rootDirectory") is None
        and project.get("nodeVersion") == "22.x"
    )
    privacy_settings_match = (
        project.get("directoryListing") is False
        and project.get("autoExposeSystemEnvs") is False
        and project.get("protectedSourcemaps") is True
        and isinstance(features, dict)
        and features.get("webAnalytics") is False
        and not integrations
        and environment_names <= ALLOWED_ENVIRONMENT_VARIABLES
        and all(_safe_environment_variable(item) for item in environment_variables)
    )
    git_settings_match = (
        isinstance(link, dict)
        and link.get("type") == "github"
        and link.get("org") == owner
        and link.get("repo") == repository
        and str(link.get("repoId")) == github_repository_id
        and link.get("productionBranch") == "main"
        and link.get("deployHooks") == []
    )
    return {
        "project_id": expectation.project_id,
        "project_name": expectation.project_name,
        "release_settings_match": release_settings_match,
        "git_settings_match": git_settings_match,
        "privacy_settings_match": privacy_settings_match,
        "web_analytics_enabled": isinstance(features, dict)
        and features.get("webAnalytics") is True,
        "integration_count": len(integrations),
        "configured_environment_variable_names": sorted(environment_names),
        "passed": release_settings_match and git_settings_match and privacy_settings_match,
    }


def _environment_names(items: list[dict[str, object]]) -> set[str]:
    names: set[str] = set()
    for item in items:
        key = item.get("key")
        if not isinstance(key, str) or not key or key in names:
            raise ValueError("Vercel environment variables require unique names")
        names.add(key)
    return names


def _safe_environment_variable(item: dict[str, object]) -> bool:
    target = item.get("target")
    if target == "production":
        target = [target]
    return (
        item.get("key") == "VITE_INFERENCE_API_URL"
        and item.get("type") == "plain"
        and target == ["production"]
        and item.get("gitBranch") in (None, "")
        and item.get("configurationId") in (None, "")
        and item.get("edgeConfigId") in (None, "")
    )


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"Vercel API {label} must be an object")
    return value


def _object_list(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"Vercel API {label} must be an object list")
    return value


def _project_argument(value: str) -> ProjectExpectation:
    project_id, separator, project_name = value.partition(":")
    if not separator:
        raise argparse.ArgumentTypeError("Project must use PROJECT_ID:PROJECT_NAME")
    return ProjectExpectation(project_id=project_id, project_name=project_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit fail-closed Vercel project controls")
    parser.add_argument("--team-id", required=True)
    parser.add_argument("--github-repository", required=True)
    parser.add_argument("--github-repository-id", required=True)
    parser.add_argument("--project", action="append", required=True, type=_project_argument)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        report = audit_vercel_projects(
            VercelProjectClient(arguments.team_id, os.environ.get("VERCEL_TOKEN", "")),
            tuple(arguments.project),
            arguments.github_repository,
            arguments.github_repository_id,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not report["passed"]:
        print("Vercel projects are not release-ready", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
