import argparse
import json
import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

UNTRUSTED_ORIGIN = "https://untrusted.invalid"
MODEL_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_FRONTEND_SCRIPTS = 10
MAX_SCRIPT_BYTES = 5 * 1024 * 1024


class _ModuleScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        attributes = dict(attrs)
        source = attributes.get("src")
        if attributes.get("type") == "module" and source:
            self.sources.append(source)


@dataclass(frozen=True)
class SmokeCheck:
    name: str
    passed: bool
    status_code: int | None
    result: str


@dataclass(frozen=True)
class SmokeReport:
    schema_version: str
    environment: str
    frontend_host: str
    api_host: str
    expected_model_version: str
    checks: tuple[SmokeCheck, ...]
    passed: bool


def validate_target(
    environment: str,
    frontend_url: str,
    api_url: str,
    expected_origin: str,
    expected_model_version: str,
) -> tuple[str, str]:
    if environment not in {"staging", "production"}:
        raise ValueError("Environment must be staging or production")
    frontend_origin = _https_origin(frontend_url, "Frontend URL")
    api_origin = _https_origin(api_url, "API URL")
    configured_origin = _https_origin(expected_origin, "Expected origin")
    if configured_origin != frontend_origin:
        raise ValueError("Expected origin must exactly match the frontend origin")
    if (urlparse(api_origin).hostname or "").endswith(".run.app"):
        raise ValueError("Smoke tests must use the load-balanced API origin, not run.app")
    if (
        not MODEL_VERSION_PATTERN.fullmatch(expected_model_version)
        or expected_model_version == "unavailable"
    ):
        raise ValueError("An immutable expected model version is required")
    return frontend_origin, api_origin


def run_smoke(
    *,
    environment: str,
    frontend_url: str,
    api_url: str,
    expected_origin: str,
    expected_model_version: str,
    transport: httpx.BaseTransport | None = None,
) -> SmokeReport:
    frontend_origin, api_origin = validate_target(
        environment,
        frontend_url,
        api_url,
        expected_origin,
        expected_model_version,
    )
    checks: list[SmokeCheck] = []
    with httpx.Client(transport=transport, timeout=20.0, follow_redirects=False) as client:
        health = _request(client, "GET", f"{api_origin}/health")
        checks.append(_json_identity_check("api_health", health, "ok", expected_model_version))

        ready = _request(client, "GET", f"{api_origin}/ready")
        checks.append(_json_identity_check("api_readiness", ready, "ok", expected_model_version))

        trusted = _request(
            client,
            "OPTIONS",
            f"{api_origin}/v1/measure",
            headers={
                "Origin": frontend_origin,
                "Access-Control-Request-Method": "POST",
            },
        )
        trusted_passed = bool(
            trusted is not None
            and trusted.status_code == 200
            and trusted.headers.get("access-control-allow-origin") == frontend_origin
            and "access-control-allow-credentials" not in trusted.headers
        )
        checks.append(
            SmokeCheck(
                "cors_trusted_origin",
                trusted_passed,
                _status(trusted),
                "exact_origin_allowed" if trusted_passed else "cors_contract_failed",
            )
        )

        untrusted = _request(
            client,
            "OPTIONS",
            f"{api_origin}/v1/measure",
            headers={
                "Origin": UNTRUSTED_ORIGIN,
                "Access-Control-Request-Method": "POST",
            },
        )
        untrusted_passed = bool(
            untrusted is not None
            and untrusted.status_code >= 400
            and "access-control-allow-origin" not in untrusted.headers
        )
        checks.append(
            SmokeCheck(
                "cors_untrusted_origin",
                untrusted_passed,
                _status(untrusted),
                "untrusted_origin_rejected" if untrusted_passed else "cors_rejection_failed",
            )
        )

        malformed = _request(
            client,
            "POST",
            f"{api_origin}/v1/measure",
            files={"image": ("smoke-invalid.jpg", b"not-an-image", "image/jpeg")},
            data={"capture_type": "left_thumb", "reference_type": "iso_id1"},
        )
        malformed_passed = bool(
            malformed is not None
            and malformed.status_code == 415
            and malformed.headers.get("cache-control") == "no-store"
            and malformed.headers.get("x-request-id")
        )
        checks.append(
            SmokeCheck(
                "malformed_upload_rejected",
                malformed_passed,
                _status(malformed),
                "typed_no_store_rejection" if malformed_passed else "upload_contract_failed",
            )
        )

        frontend = _request(client, "GET", f"{frontend_origin}/")
        frontend_passed = bool(
            frontend is not None
            and frontend.status_code == 200
            and "text/html" in frontend.headers.get("content-type", "")
            and frontend.headers.get("x-content-type-options") == "nosniff"
            and frontend.headers.get("x-frame-options") == "DENY"
            and frontend.headers.get("referrer-policy") == "no-referrer"
            and frontend.headers.get("cross-origin-opener-policy") == "same-origin"
            and frontend.headers.get("cross-origin-resource-policy") == "same-site"
            and "max-age=" in frontend.headers.get("strict-transport-security", "")
            and "frame-ancestors 'none'" in frontend.headers.get("content-security-policy", "")
            and "camera=(self)" in frontend.headers.get("permissions-policy", "")
        )
        checks.append(
            SmokeCheck(
                "frontend_security_headers",
                frontend_passed,
                _status(frontend),
                "security_headers_present" if frontend_passed else "frontend_contract_failed",
            )
        )

        bundle_passed, bundle_status = _verify_frontend_api_binding(
            client,
            frontend,
            frontend_origin,
            api_origin,
        )
        checks.append(
            SmokeCheck(
                "frontend_api_binding",
                bundle_passed,
                bundle_status,
                "exact_api_origin_embedded" if bundle_passed else "api_binding_failed",
            )
        )

    return SmokeReport(
        schema_version="nailsize-deployment-smoke@2",
        environment=environment,
        frontend_host=urlparse(frontend_origin).hostname or "",
        api_host=urlparse(api_origin).hostname or "",
        expected_model_version=expected_model_version,
        checks=tuple(checks),
        passed=all(check.passed for check in checks),
    )


def _request(client: httpx.Client, method: str, url: str, **kwargs: Any) -> httpx.Response | None:
    try:
        return client.request(method, url, **kwargs)
    except httpx.HTTPError:
        return None


def _verify_frontend_api_binding(
    client: httpx.Client,
    frontend: httpx.Response | None,
    frontend_origin: str,
    api_origin: str,
) -> tuple[bool, int | None]:
    if frontend is None or frontend.status_code != 200:
        return False, _status(frontend)
    parser = _ModuleScriptParser()
    try:
        parser.feed(frontend.text)
    except (UnicodeError, ValueError):
        return False, frontend.status_code
    sources = parser.sources[: MAX_FRONTEND_SCRIPTS + 1]
    if not sources or len(sources) > MAX_FRONTEND_SCRIPTS:
        return False, frontend.status_code

    observed_status: int | None = frontend.status_code
    for source in sources:
        script_url = urljoin(f"{frontend_origin}/", source)
        parsed = urlparse(script_url)
        if (
            f"{parsed.scheme}://{parsed.netloc}" != frontend_origin
            or parsed.username is not None
            or parsed.password is not None
        ):
            continue
        matched, observed_status = _script_has_api_binding(client, script_url, api_origin)
        if matched:
            return True, observed_status
    return False, observed_status


def _script_has_api_binding(
    client: httpx.Client, script_url: str, api_origin: str
) -> tuple[bool, int | None]:
    try:
        with client.stream("GET", script_url) as response:
            status_code = response.status_code
            if (
                status_code != 200
                or "javascript" not in response.headers.get("content-type", "").lower()
            ):
                return False, status_code
            content = bytearray()
            for chunk in response.iter_bytes():
                if len(content) + len(chunk) > MAX_SCRIPT_BYTES:
                    return False, status_code
                content.extend(chunk)
    except httpx.HTTPError:
        return False, None
    return api_origin.encode() in content and b"/v1/measure" in content, status_code


def _json_identity_check(
    name: str,
    response: httpx.Response | None,
    expected_status: str,
    expected_model_version: str,
) -> SmokeCheck:
    payload: Any = None
    if response is not None:
        try:
            payload = response.json()
        except ValueError:
            payload = None
    passed = bool(
        response is not None
        and response.status_code == 200
        and response.headers.get("cache-control") == "no-store"
        and isinstance(payload, dict)
        and payload.get("status") == expected_status
        and payload.get("model_version") == expected_model_version
    )
    return SmokeCheck(
        name,
        passed,
        _status(response),
        "identity_verified" if passed else "identity_contract_failed",
    )


def _status(response: httpx.Response | None) -> int | None:
    return response.status_code if response is not None else None


def _https_origin(value: str, label: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} must be an exact HTTPS origin")
    return value.rstrip("/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a deployed NailSize release")
    parser.add_argument("--environment", required=True, choices=("staging", "production"))
    parser.add_argument("--frontend-url", required=True)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--expected-origin", required=True)
    parser.add_argument("--expected-model-version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        report = run_smoke(
            environment=arguments.environment,
            frontend_url=arguments.frontend_url,
            api_url=arguments.api_url,
            expected_origin=arguments.expected_origin,
            expected_model_version=arguments.expected_model_version,
        )
    except ValueError as error:
        parser.error(str(error))
    rendered = json.dumps(asdict(report), indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
