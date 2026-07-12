from urllib.parse import parse_qs, urlparse

import pytest

from scripts.verify_vercel_deployment import deploy_and_verify_vercel

COMMIT_SHA = "a" * 40
AUTH_VALUE = "unit-test-access-value"


def _deployment(*, state="READY", substate="PROMOTED", sha=COMMIT_SHA):
    return {
        "id": "dpl_release123",
        "url": "nailsize-release.vercel.app",
        "projectId": "prj_nailsize",
        "target": "production",
        "readyState": state,
        "readySubstate": substate,
        "gitSource": {
            "type": "github",
            "repoId": "123456789",
            "ref": "main",
            "sha": sha,
        },
    }


def _environment_update(**overrides):
    created = {
        "key": "VITE_INFERENCE_API_URL",
        "value": "https://api.nailsize.example",
        "type": "plain",
        "target": ["production"],
    }
    created.update(overrides)
    return {"created": created, "failed": []}


def _arguments(request_json):
    return {
        "token": AUTH_VALUE,
        "project_id": "prj_nailsize",
        "project_name": "nailsize-ai",
        "team_id": "team_nailsize",
        "github_repo_id": "123456789",
        "commit_sha": COMMIT_SHA,
        "api_url": "https://api.nailsize.example",
        "frontend_url": "https://nailsize.example",
        "request_json": request_json,
    }


def test_creates_and_verifies_exact_promoted_git_deployment() -> None:
    requests = []

    def request(method, endpoint, token, body):
        requests.append((method, endpoint, token, body))
        if "/env?" in endpoint:
            return _environment_update()
        return _deployment(state="BUILDING", substate=None) if method == "POST" else _deployment()

    report = deploy_and_verify_vercel(**_arguments(request))

    method, endpoint, token, body = requests[0]
    assert method == "POST"
    assert token == AUTH_VALUE
    assert "/v10/projects/prj_nailsize/env?" in endpoint
    assert parse_qs(urlparse(endpoint).query) == {
        "teamId": ["team_nailsize"],
        "upsert": ["true"],
    }
    assert body == {
        "key": "VITE_INFERENCE_API_URL",
        "value": "https://api.nailsize.example",
        "type": "plain",
        "target": ["production"],
        "comment": "Release-bound NailSize inference origin",
    }

    method, endpoint, token, body = requests[1]
    assert method == "POST"
    assert token == AUTH_VALUE
    assert parse_qs(urlparse(endpoint).query) == {
        "teamId": ["team_nailsize"],
        "forceNew": ["1"],
    }
    assert body == {
        "name": "nailsize-ai",
        "project": "prj_nailsize",
        "target": "production",
        "gitSource": {
            "type": "github",
            "repoId": "123456789",
            "ref": "main",
            "sha": COMMIT_SHA,
        },
        "meta": {"nailsizeApprovedCommit": COMMIT_SHA},
    }
    assert requests[2][0] == "GET"
    assert "/v13/deployments/dpl_release123?" in requests[2][1]
    assert report["deployment_id"] == "dpl_release123"
    assert report["git_commit_sha"] == COMMIT_SHA
    assert report["ready_substate"] == "PROMOTED"


def test_rejects_terminal_deployment_failure() -> None:
    def request(method, endpoint, _token, _body):
        if "/env?" in endpoint:
            return _environment_update()
        return _deployment(state="BUILDING") if method == "POST" else _deployment(state="ERROR")

    with pytest.raises(RuntimeError, match="terminal failure"):
        deploy_and_verify_vercel(**_arguments(request))


def test_rejects_identity_change_while_polling() -> None:
    def request(method, endpoint, _token, _body):
        if "/env?" in endpoint:
            return _environment_update()
        return _deployment(state="BUILDING") if method == "POST" else _deployment(sha="b" * 40)

    with pytest.raises(ValueError, match="Git SHA"):
        deploy_and_verify_vercel(**_arguments(request))


def test_times_out_when_exact_deployment_is_not_promoted() -> None:
    ticks = iter((0.0, 0.0))

    def request(_method, endpoint, _token, _body):
        if "/env?" in endpoint:
            return _environment_update()
        return _deployment(state="READY", substate="STAGED")

    with pytest.raises(TimeoutError, match="did not become promoted"):
        deploy_and_verify_vercel(
            **_arguments(request),
            timeout_seconds=0,
            monotonic=lambda: next(ticks),
            sleep=lambda _seconds: None,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"token": ""},
        {"github_repo_id": "owner/repo"},
        {"commit_sha": "main"},
        {"api_url": "http://api.nailsize.example"},
        {"api_url": "https://api.nailsize.example/path"},
        {"frontend_url": "http://nailsize.example"},
        {"frontend_url": "https://nailsize.example/path"},
    ],
)
def test_rejects_ambiguous_or_insecure_inputs(overrides) -> None:
    arguments = _arguments(lambda *_args: _deployment())
    arguments.update(overrides)
    with pytest.raises(ValueError):
        deploy_and_verify_vercel(**arguments)


@pytest.mark.parametrize(
    "response",
    [
        {"created": _environment_update()["created"], "failed": [{"error": {}}]},
        {"created": [], "failed": []},
        _environment_update(value="https://wrong.example"),
        _environment_update(type="sensitive"),
        _environment_update(target=["preview"]),
    ],
)
def test_rejects_incomplete_or_mismatched_api_origin_update(response) -> None:
    def request(_method, endpoint, _token, _body):
        if "/env?" in endpoint:
            return response
        return _deployment()

    with pytest.raises(ValueError, match="environment update"):
        deploy_and_verify_vercel(**_arguments(request))
