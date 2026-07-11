import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

TERMINAL_FAILURE_STATES = frozenset({"BLOCKED", "CANCELED", "ERROR"})


def deploy_and_verify_vercel(
    *,
    token: str,
    project_id: str,
    project_name: str,
    team_id: str,
    github_repo_id: str,
    commit_sha: str,
    frontend_url: str,
    timeout_seconds: float = 1200,
    poll_interval_seconds: float = 10,
    request_json: Callable[[str, str, str, dict[str, Any] | None], dict[str, Any]] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    _validate_inputs(
        token,
        project_id,
        project_name,
        team_id,
        github_repo_id,
        commit_sha,
        frontend_url,
    )
    request = request_json or _request_json
    create_endpoint = "https://api.vercel.com/v13/deployments?" + urllib.parse.urlencode(
        {"teamId": team_id, "forceNew": "1"}
    )
    git_source = {
        "type": "github",
        "repoId": github_repo_id,
        "ref": "main",
        "sha": commit_sha,
    }
    created = request(
        "POST",
        create_endpoint,
        token,
        {
            "name": project_name,
            "project": project_id,
            "target": "production",
            "gitSource": git_source,
            "meta": {"nailsizeApprovedCommit": commit_sha},
        },
    )
    deployment_id = created.get("id")
    if not isinstance(deployment_id, str) or not deployment_id:
        raise ValueError("Vercel did not return an immutable deployment ID")
    _validate_deployment_identity(created, project_id, github_repo_id, commit_sha, deployment_id)

    status_endpoint = (
        f"https://api.vercel.com/v13/deployments/{urllib.parse.quote(deployment_id, safe='')}?"
        + urllib.parse.urlencode({"teamId": team_id, "withGitRepoInfo": "true"})
    )
    deadline = monotonic() + timeout_seconds
    while True:
        deployment = request("GET", status_endpoint, token, None)
        _validate_deployment_identity(
            deployment, project_id, github_repo_id, commit_sha, deployment_id
        )
        state = deployment.get("readyState") or deployment.get("status")
        if state == "READY" and deployment.get("readySubstate") == "PROMOTED":
            generated_url = deployment.get("url")
            if not isinstance(generated_url, str) or not generated_url:
                raise ValueError("Ready Vercel deployment has no generated URL")
            return {
                "schema_version": "nailsize-vercel-deployment@1",
                "deployment_id": deployment_id,
                "generated_url": f"https://{generated_url}",
                "frontend_url": frontend_url,
                "git_commit_sha": commit_sha,
                "project_id": project_id,
                "ready_state": "READY",
                "ready_substate": "PROMOTED",
                "target": "production",
            }
        if state in TERMINAL_FAILURE_STATES:
            raise RuntimeError(f"Vercel deployment reached terminal failure state: {state}")
        if monotonic() >= deadline:
            raise TimeoutError("The approved Vercel production deployment did not become promoted")
        sleep(poll_interval_seconds)


def _validate_deployment_identity(
    deployment: dict[str, Any],
    project_id: str,
    github_repo_id: str,
    commit_sha: str,
    deployment_id: str,
) -> None:
    if deployment.get("id") != deployment_id or deployment.get("projectId") != project_id:
        raise ValueError("Vercel deployment identity does not match the approved project")
    if deployment.get("target") != "production":
        raise ValueError("Vercel deployment is not a production target")
    git_source = deployment.get("gitSource")
    if not isinstance(git_source, dict) or git_source.get("type") != "github":
        raise ValueError("Vercel deployment is not backed by the approved GitHub repository")
    if str(git_source.get("repoId")) != github_repo_id:
        raise ValueError("Vercel deployment GitHub repository ID does not match")
    if git_source.get("sha") != commit_sha:
        raise ValueError("Vercel deployment Git SHA does not match the approved commit")


def _validate_inputs(
    token: str,
    project_id: str,
    project_name: str,
    team_id: str,
    github_repo_id: str,
    commit_sha: str,
    frontend_url: str,
) -> None:
    values = (token, project_id, project_name, team_id, github_repo_id)
    if any(not value.strip() for value in values):
        raise ValueError("Vercel authentication and project/repository identifiers are required")
    if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in project_name):
        raise ValueError("Vercel project name contains unsupported characters")
    if not github_repo_id.isdigit():
        raise ValueError("GitHub repository ID must be numeric")
    if len(commit_sha) != 40 or any(
        character not in "0123456789abcdef" for character in commit_sha
    ):
        raise ValueError("Git commit SHA must be 40 lowercase hexadecimal characters")
    parsed = urlparse(frontend_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.path not in ("", "/")
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Frontend URL must be an exact HTTPS origin")


def _request_json(
    method: str, endpoint: str, token: str, body: dict[str, Any] | None
) -> dict[str, Any]:
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or parsed.hostname != "api.vercel.com":
        raise ValueError("Vercel API endpoint must use the expected HTTPS host")
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 -- endpoint is restricted above.
        endpoint,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            payload = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError("Vercel deployment API request failed") from error
    if not isinstance(payload, dict):
        raise ValueError("Vercel response must be a JSON object")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create and verify an approved Vercel Git deployment without the CLI"
    )
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--team-id", required=True)
    parser.add_argument("--github-repo-id", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--frontend-url", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=1200)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    report = deploy_and_verify_vercel(
        token=os.environ.get("VERCEL_TOKEN", ""),
        project_id=arguments.project_id,
        project_name=arguments.project_name,
        team_id=arguments.team_id,
        github_repo_id=arguments.github_repo_id,
        commit_sha=arguments.commit_sha,
        frontend_url=arguments.frontend_url,
        timeout_seconds=arguments.timeout_seconds,
    )
    output = os.path.abspath(arguments.output)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as destination:
        json.dump(report, destination, indent=2, sort_keys=True)
        destination.write("\n")


if __name__ == "__main__":
    main()
