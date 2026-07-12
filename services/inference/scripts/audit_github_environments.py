"""Audit GitHub deployment environments without reading secret values."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

SCHEMA_VERSION = "nailsize-github-environment-audit@1"
EXPECTED_ENVIRONMENTS = ("development", "staging", "production")
DEPLOYMENT_ENVIRONMENTS = ("staging", "production")
REQUIRED_VARIABLE_NAMES = frozenset(
    {
        "API_DOMAIN",
        "BILLING_ACCOUNT_ID",
        "BUDGET_CURRENCY",
        "BUDGET_THRESHOLDS_JSON",
        "DELETION_PROTECTION",
        "ERROR_RATE_THRESHOLD",
        "FRONTEND_ORIGIN",
        "GCP_DEPLOY_SERVICE_ACCOUNT",
        "GCP_PROJECT_ID",
        "GCP_REGION",
        "GCP_WORKLOAD_IDENTITY_PROVIDER",
        "MALFORMED_UPLOADS_PER_MINUTE_THRESHOLD",
        "MAX_INSTANCES",
        "MONITORING_NOTIFICATION_CHANNEL_IDS_JSON",
        "MONTHLY_BUDGET_UNITS",
        "P95_LATENCY_THRESHOLD_MS",
        "RATE_LIMIT_INTERVAL_SECONDS",
        "RATE_LIMIT_PREVIEW",
        "RATE_LIMIT_REQUESTS",
        "TF_STATE_BUCKET",
        "VERCEL_GITHUB_REPO_ID",
        "VERCEL_PROJECT_ID",
        "VERCEL_PROJECT_NAME",
        "VERCEL_TEAM_ID",
    }
)
REQUIRED_SECRET_NAMES = frozenset({"VERCEL_TOKEN"})
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_MAX_RESPONSE_BYTES = 1_000_000


class EnvironmentClient(Protocol):
    repository: str

    def get_json(self, suffix: str) -> dict[str, object]: ...


class GitHubEnvironmentClient:
    def __init__(self, repository: str, token: str) -> None:
        if _REPOSITORY.fullmatch(repository) is None:
            raise ValueError("Repository must use the OWNER/REPOSITORY form")
        if not token.strip():
            raise ValueError("GITHUB_TOKEN is required")
        self.repository = repository
        self._token = token

    def get_json(self, suffix: str) -> dict[str, object]:
        if not suffix.startswith("/") or "//" in suffix:
            raise ValueError("GitHub API suffix must be a repository-relative absolute path")
        url = f"https://api.github.com/repos/{self.repository}{suffix}"
        request = Request(  # noqa: S310 - URL is constructed from a fixed HTTPS API host
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "nailsize-environment-audit",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed HTTPS host
                payload = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            raise RuntimeError(
                f"GitHub API returned HTTP {error.code} for {suffix.split('?', 1)[0]}"
            ) from None
        except URLError as error:
            raise RuntimeError(
                "GitHub API request failed before a response was received"
            ) from error
        if len(payload) > _MAX_RESPONSE_BYTES:
            raise ValueError("GitHub API response exceeded the audit size limit")
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise ValueError("GitHub API response must be a JSON object")
        return parsed


def audit_github_environments(client: EnvironmentClient) -> dict[str, object]:
    listing = client.get_json("/environments?per_page=100")
    environments = _object_list(listing, "environments")
    total_count = _nonnegative_int(listing, "total_count")
    if total_count != len(environments):
        raise ValueError("Environment listing must fit in one complete audit page")

    by_name: dict[str, dict[str, object]] = {}
    for environment in environments:
        name = environment.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("Every GitHub environment requires a name")
        if name in by_name:
            raise ValueError(f"Duplicate GitHub environment: {name}")
        by_name[name] = environment

    expected = set(EXPECTED_ENVIRONMENTS)
    unexpected_names = sorted(set(by_name) - expected)
    results = [
        _audit_environment(client, name, by_name.get(name)) for name in EXPECTED_ENVIRONMENTS
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "repository": client.repository,
        "expected_environment_names": list(EXPECTED_ENVIRONMENTS),
        "unexpected_environment_names": unexpected_names,
        "environments": results,
        "passed": not unexpected_names and all(result["passed"] for result in results),
    }


def _audit_environment(
    client: EnvironmentClient, name: str, environment: dict[str, object] | None
) -> dict[str, object]:
    if environment is None:
        return {"name": name, "exists": False, "passed": False}

    encoded_name = quote(name, safe="")
    variable_names, variable_error = _read_named_page(
        client, f"/environments/{encoded_name}/variables?per_page=100", "variables"
    )
    secret_names, secret_error = _read_named_page(
        client, f"/environments/{encoded_name}/secrets?per_page=100", "secrets"
    )
    metadata_errors = [error for error in (variable_error, secret_error) if error]

    if name == "development":
        result: dict[str, object] = {
            "name": name,
            "exists": True,
            "passed": not metadata_errors and variable_names == set() and secret_names == set(),
        }
        if variable_names is not None:
            result["configured_variable_names"] = sorted(variable_names)
        if secret_names is not None:
            result["configured_secret_names"] = sorted(secret_names)
        if metadata_errors:
            result["metadata_errors"] = metadata_errors
        return result

    rules = _object_list(environment, "protection_rules")
    reviewer_rules = [rule for rule in rules if rule.get("type") == "required_reviewers"]
    reviewer_count = 0
    prevent_self_review = False
    if len(reviewer_rules) == 1:
        reviewers = reviewer_rules[0].get("reviewers")
        if isinstance(reviewers, list):
            reviewer_count = len(reviewers)
        prevent_self_review = reviewer_rules[0].get("prevent_self_review") is True

    deployment_policy = environment.get("deployment_branch_policy")
    policy_names: set[str] = set()
    if (
        isinstance(deployment_policy, dict)
        and deployment_policy.get("custom_branch_policies") is True
    ):
        policy_names_result, policy_error = _read_named_page(
            client,
            f"/environments/{encoded_name}/deployment-branch-policies?per_page=100",
            "branch_policies",
        )
        if policy_error:
            metadata_errors.append(policy_error)
        if policy_names_result is not None:
            policy_names = policy_names_result
    main_only = (
        isinstance(deployment_policy, dict)
        and deployment_policy.get("protected_branches") is False
        and deployment_policy.get("custom_branch_policies") is True
        and policy_names == {"main"}
    )
    missing_variables = (
        sorted(REQUIRED_VARIABLE_NAMES - variable_names) if variable_names is not None else None
    )
    unexpected_variables = (
        sorted(variable_names - REQUIRED_VARIABLE_NAMES) if variable_names is not None else None
    )
    missing_secrets = (
        sorted(REQUIRED_SECRET_NAMES - secret_names) if secret_names is not None else None
    )
    unexpected_secrets = (
        sorted(secret_names - REQUIRED_SECRET_NAMES) if secret_names is not None else None
    )
    protected = (
        len(reviewer_rules) == 1
        and reviewer_count >= 1
        and main_only
        and (name != "production" or prevent_self_review)
    )
    passed = (
        not metadata_errors
        and not any(
            (
                missing_variables,
                unexpected_variables,
                missing_secrets,
                unexpected_secrets,
            )
        )
        and protected
    )
    result = {
        "name": name,
        "exists": True,
        "required_reviewer_count": reviewer_count,
        "prevent_self_review": prevent_self_review,
        "deployment_branch_names": sorted(policy_names),
        "passed": passed,
    }
    if variable_names is not None:
        result.update(
            {
                "configured_variable_names": sorted(variable_names),
                "missing_variable_names": missing_variables,
                "unexpected_variable_names": unexpected_variables,
            }
        )
    if secret_names is not None:
        result.update(
            {
                "configured_secret_names": sorted(secret_names),
                "missing_secret_names": missing_secrets,
                "unexpected_secret_names": unexpected_secrets,
            }
        )
    if metadata_errors:
        result["metadata_errors"] = metadata_errors
    return result


def _read_named_page(
    client: EnvironmentClient, suffix: str, key: str
) -> tuple[set[str] | None, str | None]:
    try:
        return _named_page(client.get_json(suffix), key), None
    except RuntimeError as error:
        return None, str(error)


def _named_page(payload: dict[str, object], key: str) -> set[str]:
    entries = _object_list(payload, key)
    total_count = _nonnegative_int(payload, "total_count")
    if total_count != len(entries):
        raise ValueError(f"{key} listing must fit in one complete audit page")
    names: set[str] = set()
    for entry in entries:
        name = entry.get("name")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError(f"{key} entries require unique names")
        names.add(name)
    return names


def _object_list(payload: dict[str, object], key: str) -> list[dict[str, object]]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"GitHub API field {key} must be an object list")
    return value


def _nonnegative_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"GitHub API field {key} must be a nonnegative integer")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit fail-closed GitHub deployment environment configuration"
    )
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        client = GitHubEnvironmentClient(
            arguments.repository,
            os.environ.get("GITHUB_TOKEN", ""),
        )
        report = audit_github_environments(client)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not report["passed"]:
        print("GitHub deployment environments are not release-ready", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
