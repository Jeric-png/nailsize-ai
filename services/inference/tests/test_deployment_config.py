import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_vercel_config_preserves_build_routing_and_security_headers() -> None:
    config = json.loads((REPOSITORY_ROOT / "vercel.json").read_text())
    assert config["buildCommand"] == "npm run build"
    assert config["outputDirectory"] == "apps/web/dist"
    assert config["git"] == {"deploymentEnabled": {"main": False}}
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
        "value: ${SEGMENTATION_BOUNDARY_ERROR_PX}",
    ]

    for setting in required_settings:
        assert setting in manifest


def test_container_requires_both_runtime_models_and_native_landmark_dependencies() -> None:
    inference_root = REPOSITORY_ROOT / "services" / "inference"
    dockerfile = (inference_root / "Dockerfile").read_text()
    dockerignore = (inference_root / ".dockerignore").read_text()

    for package in ("libegl1", "libgl1", "libgles2", "libglib2.0-0"):
        assert package in dockerfile
    assert "pip install '.[landmarks]'" in dockerfile
    assert "COPY models/hand_landmarker.task" in dockerfile
    assert "COPY models/nail-segmentation.onnx" in dockerfile
    assert "!models/hand_landmarker.task" in dockerignore
    assert "!models/nail-segmentation.onnx" in dockerignore


def test_container_ci_runs_read_only_and_checks_termination_diff() -> None:
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    dockerfile = (REPOSITORY_ROOT / "services" / "inference" / "Dockerfile").read_text()
    container_step = workflow.split("- name: Build and privacy-smoke the runtime image", 1)[1]

    for contract in (
        "--read-only",
        "--cap-drop ALL",
        "--security-opt no-new-privileges",
        "--tmpfs /tmp:rw,noexec,nosuid,size=16m",
        'test "$status" = 415',
        "docker stop --time 1 nailsize-contract",
        'test -z "$(docker diff nailsize-contract)"',
    ):
        assert contract in container_step
    assert "MPLCONFIGDIR=/tmp/matplotlib" in dockerfile


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


def test_deployment_smoke_workflow_is_reusable_and_preserves_safe_evidence() -> None:
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "deployment-smoke.yml").read_text()

    assert "workflow_call:" in workflow
    assert "workflow_dispatch:" in workflow
    for required_input in (
        "environment:",
        "frontend_url:",
        "api_url:",
        "expected_origin:",
        "expected_model_version:",
    ):
        assert workflow.count(required_input) >= 2
    assert "services/inference/scripts/deployment_smoke.py" in workflow
    assert "retention-days: 30" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd" in workflow
    assert "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1" in workflow
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in workflow


def test_deployment_workflow_is_manual_gated_and_verifies_before_cloud_auth() -> None:
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "deploy.yml").read_text()

    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "\n  push:" not in workflow
    assert "actions: read\n  contents: read\n  id-token: write" in workflow
    assert "environment: ${{ inputs.environment }}" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "PRODUCTION_CONFIRMATION" in workflow
    assert "DEPLOY_PRODUCTION" in workflow
    assert "STAGING_RUN_ID" in workflow
    assert "deployment-evidence-staging" in workflow
    assert "deployment-smoke-staging" in workflow
    assert "verify_staging_promotion.py" in workflow
    assert "verify_image_promotion.py" in workflow
    assert "verify_cloud_run_benchmark.py" in workflow
    assert "work/onnx-runtime-benchmark.json" in workflow
    assert 'gcloud run jobs execute "$benchmark_job"' in workflow
    assert r"jsonPayload.schema_version=\"nailsize-cloud-run-onnx-benchmark-sample@1\"" in workflow
    assert 'gh run list --repo "$GITHUB_REPOSITORY" --workflow CI' in workflow
    assert "google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093" in workflow
    assert "google-github-actions/setup-gcloud@aa5489c8933f4cc7a4f7d45035b3b1440c9c10db" in workflow
    assert "credentials_json" not in workflow
    assert "npx vercel" not in workflow
    assert "npm install vercel" not in workflow
    assert "uses: ./.github/workflows/deployment-smoke.yml" in workflow

    staging_gate = workflow.index("verify_staging_promotion.py")
    release_gate = workflow.index("nailsize-release-bundle")
    runtime_gate = workflow.index("verify_runtime_model.py")
    vercel_gate = workflow.index("verify_vercel_deployment.py")
    cloud_auth = workflow.index("google-github-actions/auth@")
    image_promotion = workflow.index('docker pull "$source_image"')
    image_build = workflow.index('docker build --tag "$image_tag"')
    observability_apply = workflow.index("terraform -chdir=infra/observability apply")
    runtime_benchmark = workflow.index("verify_cloud_run_benchmark.py")
    assert (
        staging_gate
        < release_gate
        < runtime_gate
        < cloud_auth
        < image_promotion
        < runtime_benchmark
        < observability_apply
        < vercel_gate
    )
    assert image_promotion < image_build
    image_step = workflow.split("- name: Build or promote immutable inference image", 1)[1].split(
        "- name: Apply API platform", 1
    )[0]
    production_branch = image_step.split('if [[ "$DEPLOY_ENVIRONMENT" == "production" ]]; then', 1)[
        1
    ].split("          else", 1)[0]
    staging_branch = image_step.split("          else", 1)[1].split("          fi", 1)[0]
    assert "docker build" not in production_branch
    assert 'docker build --tag "$image_tag" services/inference' in staging_branch
    assert 'docker tag "$source_image" "$image_tag"' in workflow
    assert '--source-image-uri "$source_image"' in workflow
    assert "work/image-promotion.json" in workflow
    assert '--arg schema_version "nailsize-deployment@3"' in workflow


def test_cloud_run_benchmark_job_matches_service_cpu_and_model_contract() -> None:
    main = (REPOSITORY_ROOT / "infra" / "platform" / "main.tf").read_text()
    outputs = (REPOSITORY_ROOT / "infra" / "platform" / "outputs.tf").read_text()
    job = main.split('resource "google_cloud_run_v2_job" "onnx_benchmark"', 1)[1].split(
        'resource "google_cloud_run_v2_service_iam_member"', 1
    )[0]

    for contract in (
        'name                = "${local.prefix}-onnx-benchmark"',
        "task_count  = 1",
        "parallelism = 1",
        'timeout               = "300s"',
        "max_retries           = 0",
        'execution_environment = "EXECUTION_ENVIRONMENT_GEN2"',
        'command = ["python"]',
        'args    = ["-m", "app.runtime_benchmark"]',
        'cpu    = "2"',
        'memory = "4Gi"',
        'name  = "BENCHMARK_IMAGE_URI"',
        'name  = "MODEL_SHA256"',
        'name  = "MODEL_VERSION"',
    ):
        assert contract in job
    assert 'output "cloud_run_benchmark_job"' in outputs


def test_every_terraform_root_declares_remote_gcs_state() -> None:
    for root in ("bootstrap", "platform", "observability"):
        versions = (REPOSITORY_ROOT / "infra" / root / "versions.tf").read_text()
        assert 'backend "gcs" {}' in versions


def test_ci_runs_current_engine_compatibility_without_replacing_device_certification() -> None:
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    config = (REPOSITORY_ROOT / "playwright.compat.config.ts").read_text()
    package = json.loads((REPOSITORY_ROOT / "package.json").read_text())

    assert "browser-engines:" in workflow
    assert "playwright install --with-deps chromium firefox webkit" in workflow
    assert "npm run test:compat" in workflow
    assert package["scripts"]["test:compat"].startswith("NAILSIZE_SKIP_VISUAL_ASSERTIONS=1")
    for project in (
        "android-chromium-current",
        "ios-webkit-current",
        "desktop-chromium-current",
        "desktop-firefox-current",
        "desktop-webkit-current",
    ):
        assert project in config
