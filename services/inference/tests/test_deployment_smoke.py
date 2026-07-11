import json
from dataclasses import asdict

import httpx
import pytest

from scripts.deployment_smoke import MAX_SCRIPT_BYTES, run_smoke, validate_target

FRONTEND = "https://staging.nailsize.example"
API = "https://api-staging.nailsize.example"
MODEL_VERSION = "baseline-20260712-sha256abcd"


def deployment_transport(
    *,
    wrong_model: bool = False,
    wrong_api_binding: bool = False,
    leak_body: bool = False,
    script_source: str = "/assets/app.js",
    script_status: int = 200,
    script_content_type: str = "application/javascript",
    script_text: str | None = None,
    extra_module_scripts: int = 0,
):
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "staging.nailsize.example" and request.url.path == "/":
            scripts = (
                [f'<script type="module" src="{script_source}"></script>'] if script_source else []
            )
            scripts.extend(
                f'<script type="module" src="/assets/extra-{index}.js"></script>'
                for index in range(extra_module_scripts)
            )
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
                text=f"<html>{''.join(scripts)}</html>",
            )
        if request.url.host == "staging.nailsize.example" and request.url.path == "/assets/app.js":
            bound_api = "https://wrong-api.example" if wrong_api_binding else API
            return httpx.Response(
                script_status,
                headers={"content-type": script_content_type},
                text=(
                    script_text
                    if script_text is not None
                    else f'const apiUrl="{bound_api}";fetch(`${{apiUrl}}/v1/measure`);'
                ),
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
    assert report.schema_version == "nailsize-deployment-smoke@2"
    assert len(report.checks) == 7
    assert all(check.passed for check in report.checks)


def test_wrong_deployed_api_binding_fails_closed() -> None:
    report = run_smoke(
        environment="staging",
        frontend_url=FRONTEND,
        api_url=API,
        expected_origin=FRONTEND,
        expected_model_version=MODEL_VERSION,
        transport=deployment_transport(wrong_api_binding=True),
    )

    assert report.passed is False
    assert [check.name for check in report.checks if not check.passed] == ["frontend_api_binding"]


@pytest.mark.parametrize(
    "transport_arguments",
    [
        {"script_source": ""},
        {"script_source": "https://cdn.example/app.js"},
        {"script_status": 503},
        {"script_content_type": "text/plain"},
        {"script_text": "x" * (MAX_SCRIPT_BYTES + 1)},
        {"extra_module_scripts": 10},
    ],
)
def test_unsafe_or_ambiguous_frontend_bundles_fail_closed(transport_arguments) -> None:
    report = run_smoke(
        environment="staging",
        frontend_url=FRONTEND,
        api_url=API,
        expected_origin=FRONTEND,
        expected_model_version=MODEL_VERSION,
        transport=deployment_transport(**transport_arguments),
    )

    binding = next(check for check in report.checks if check.name == "frontend_api_binding")
    assert binding.passed is False
    assert report.passed is False


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
