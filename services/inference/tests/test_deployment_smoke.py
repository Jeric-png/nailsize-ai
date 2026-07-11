import json
from dataclasses import asdict

import httpx
import pytest

from scripts.deployment_smoke import run_smoke, validate_target

FRONTEND = "https://staging.nailsize.example"
API = "https://api-staging.nailsize.example"
MODEL_VERSION = "baseline-20260712-sha256abcd"


def deployment_transport(*, wrong_model: bool = False, leak_body: bool = False):
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "staging.nailsize.example":
            return httpx.Response(
                200,
                headers={
                    "content-type": "text/html; charset=utf-8",
                    "x-content-type-options": "nosniff",
                    "x-frame-options": "DENY",
                    "referrer-policy": "no-referrer",
                    "cross-origin-opener-policy": "same-origin",
                    "cross-origin-resource-policy": "same-site",
                    "strict-transport-security": "max-age=63072000; includeSubDomains",
                    "content-security-policy": "default-src 'self'; frame-ancestors 'none'",
                    "permissions-policy": "camera=(self), microphone=()",
                },
                text="<html>NailSize</html>",
            )
        if request.url.path in {"/health", "/ready"}:
            return httpx.Response(
                200,
                headers={"cache-control": "no-store"},
                json={
                    "status": "ok",
                    "model_version": "wrong-model" if wrong_model else MODEL_VERSION,
                    "private": "must-never-enter-report" if leak_body else "",
                },
            )
        if request.method == "OPTIONS":
            origin = request.headers["origin"]
            if origin == FRONTEND:
                return httpx.Response(200, headers={"access-control-allow-origin": FRONTEND})
            return httpx.Response(400)
        if request.method == "POST" and request.url.path == "/v1/measure":
            assert b'filename="smoke-invalid.jpg"' in request.read()
            return httpx.Response(
                415,
                headers={"cache-control": "no-store", "x-request-id": "safe-request-id"},
                json={"detail": "safe rejection"},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    return httpx.MockTransport(respond)


def test_passing_smoke_verifies_deployed_identity_privacy_cors_and_frontend() -> None:
    report = run_smoke(
        environment="staging",
        frontend_url=f"{FRONTEND}/",
        api_url=API,
        expected_origin=FRONTEND,
        expected_model_version=MODEL_VERSION,
        transport=deployment_transport(),
    )

    assert report.passed is True
    assert report.frontend_host == "staging.nailsize.example"
    assert report.api_host == "api-staging.nailsize.example"
    assert len(report.checks) == 6
    assert all(check.passed for check in report.checks)


def test_failure_report_never_copies_response_bodies() -> None:
    report = run_smoke(
        environment="staging",
        frontend_url=FRONTEND,
        api_url=API,
        expected_origin=FRONTEND,
        expected_model_version=MODEL_VERSION,
        transport=deployment_transport(wrong_model=True, leak_body=True),
    )

    rendered = json.dumps(asdict(report))
    assert report.passed is False
    assert "must-never-enter-report" not in rendered
    assert [check.name for check in report.checks if not check.passed] == [
        "api_health",
        "api_readiness",
    ]


def test_transport_failures_are_sanitized_and_fail_closed() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sensitive transport detail", request=request)

    report = run_smoke(
        environment="production",
        frontend_url="https://nailsize.example",
        api_url="https://api.nailsize.example",
        expected_origin="https://nailsize.example",
        expected_model_version=MODEL_VERSION,
        transport=httpx.MockTransport(fail),
    )

    assert report.passed is False
    assert all(check.status_code is None for check in report.checks)
    assert "sensitive" not in json.dumps(asdict(report))


@pytest.mark.parametrize(
    ("environment", "frontend", "api", "origin", "model", "message"),
    [
        ("development", FRONTEND, API, FRONTEND, MODEL_VERSION, "Environment"),
        ("staging", "http://staging.example", API, FRONTEND, MODEL_VERSION, "HTTPS"),
        ("staging", FRONTEND, "https://service.run.app:443", FRONTEND, MODEL_VERSION, "run.app"),
        ("staging", FRONTEND, API, "https://other.example", MODEL_VERSION, "exactly match"),
        ("staging", FRONTEND, API, FRONTEND, "unavailable", "model version"),
        ("staging", FRONTEND, API, FRONTEND, "model version", "model version"),
    ],
)
def test_rejects_unsafe_or_ambiguous_targets(
    environment: str,
    frontend: str,
    api: str,
    origin: str,
    model: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_target(environment, frontend, api, origin, model)
