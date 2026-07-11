import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_vercel_config_preserves_build_routing_and_security_headers() -> None:
    config = json.loads((REPOSITORY_ROOT / "vercel.json").read_text())
    assert config["buildCommand"] == "npm run build"
    assert config["outputDirectory"] == "apps/web/dist"
    assert config["rewrites"] == [{"source": "/((?!assets/).*)", "destination": "/index.html"}]

    headers = {entry["key"]: entry["value"] for entry in config["headers"][0]["headers"]}
    assert config["headers"][0]["source"] == "/(.*)"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "camera=(self)" in headers["Permissions-Policy"]


def test_cloud_run_template_preserves_fail_closed_runtime_contract() -> None:
    manifest = (REPOSITORY_ROOT / "infra/cloud-run/service.template.yaml").read_text()
    required_settings = [
        "run.googleapis.com/ingress: internal-and-cloud-load-balancing",
        'autoscaling.knative.dev/minScale: "1"',
        'autoscaling.knative.dev/maxScale: "${MAX_INSTANCES}"',
        "containerConcurrency: 1",
        "timeoutSeconds: 15",
        "serviceAccountName: ${SERVICE_ACCOUNT_EMAIL}",
        'cpu: "2"',
        "memory: 4Gi",
        "path: /ready",
        "path: /health",
        "value: ${MODEL_SHA256}",
        "value: ${MODEL_VERSION}",
    ]

    for setting in required_settings:
        assert setting in manifest


def test_environment_profiles_are_explicit_and_non_secret() -> None:
    environment_dir = REPOSITORY_ROOT / "infra/environments"
    expected = {
        "development": "http://localhost:5173",
        "staging": "https://staging.nailsize.example",
        "production": "https://nailsize.example",
    }

    for environment, origin in expected.items():
        profile = (environment_dir / f"{environment}.env.example").read_text()
        assert f"DEPLOYMENT_ENVIRONMENT={environment}" in profile
        assert f"ALLOWED_ORIGINS={origin}" in profile
        assert "API_KEY=" not in profile
        assert "TOKEN=" not in profile
