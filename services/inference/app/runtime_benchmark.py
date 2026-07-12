import hashlib
import json
import os
import re
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort

SCHEMA_VERSION = "nailsize-cloud-run-onnx-benchmark-sample@1"
INPUT_SHAPE = [1, 3, 224, 160]
OUTPUT_SHAPE = [1, 1, 224, 160]
MIN_ITERATIONS = 200
MIN_WARMUP_ITERATIONS = 20
LATENCY_LIMITS_MS = {"p50": 2_000.0, "p95": 5_000.0, "p99": 10_000.0}
_REJECTED_MODEL_MARKERS = (
    "contract",
    "fixture",
    "placeholder",
    "synthetic",
    "test-model",
    "unavailable",
)
_IMAGE_URI = re.compile(
    r"^[a-z0-9-]+-docker\.pkg\.dev/[a-z][a-z0-9-]{4,28}[a-z0-9]/"
    r"nailsize-(?P<environment>staging|production)-inference/"
    r"inference@sha256:[0-9a-f]{64}$"
)


def benchmark_runtime_model(
    *,
    environment: Mapping[str, str] | None = None,
    iterations: int = MIN_ITERATIONS,
    warmup_iterations: int = MIN_WARMUP_ITERATIONS,
) -> dict[str, Any]:
    values = os.environ if environment is None else environment
    deployment_environment = _required(values, "DEPLOYMENT_ENVIRONMENT")
    if deployment_environment not in {"staging", "production"}:
        raise ValueError("Runtime benchmark requires staging or production")
    job_name = _required(values, "CLOUD_RUN_JOB")
    execution_name = _required(values, "CLOUD_RUN_EXECUTION")
    if (
        _required(values, "CLOUD_RUN_TASK_INDEX") != "0"
        or _required(values, "CLOUD_RUN_TASK_ATTEMPT") != "0"
        or _required(values, "CLOUD_RUN_TASK_COUNT") != "1"
    ):
        raise ValueError("Runtime benchmark requires one first-attempt Cloud Run task")
    image_uri = _required(values, "BENCHMARK_IMAGE_URI")
    match = _IMAGE_URI.fullmatch(image_uri)
    if match is None or match.group("environment") != deployment_environment:
        raise ValueError("Runtime benchmark image must use the exact environment repository digest")
    model_version = _required(values, "MODEL_VERSION")
    if any(marker in model_version.lower() for marker in _REJECTED_MODEL_MARKERS):
        raise ValueError("Runtime benchmark requires a non-synthetic model version")
    model_sha256 = _required(values, "MODEL_SHA256")
    if not _valid_sha256(model_sha256):
        raise ValueError("Runtime benchmark model checksum must be lowercase SHA-256")
    if (
        isinstance(iterations, bool)
        or not isinstance(iterations, int)
        or iterations < MIN_ITERATIONS
        or isinstance(warmup_iterations, bool)
        or not isinstance(warmup_iterations, int)
        or warmup_iterations < MIN_WARMUP_ITERATIONS
    ):
        raise ValueError("Runtime benchmark requires at least 200 measured and 20 warmup runs")

    model_path = Path(_required(values, "MODEL_PATH"))
    if not model_path.is_file() or _sha256(model_path) != model_sha256:
        raise ValueError("Runtime benchmark model does not match the approved checksum")
    session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    if (
        session.get_providers() != ["CPUExecutionProvider"]
        or len(inputs) != 1
        or len(outputs) != 1
        or list(inputs[0].shape) != INPUT_SHAPE
        or list(outputs[0].shape) != OUTPUT_SHAPE
    ):
        raise ValueError("Runtime benchmark model does not satisfy the CPU tensor contract")

    tensor = np.zeros(INPUT_SHAPE, dtype=np.float32)
    feed = {inputs[0].name: tensor}
    output_names = [outputs[0].name]
    for _ in range(warmup_iterations):
        _validate_output(session.run(output_names, feed)[0])

    durations = np.empty(iterations, dtype=float)
    for index in range(iterations):
        started = time.perf_counter_ns()
        result = session.run(output_names, feed)[0]
        durations[index] = (time.perf_counter_ns() - started) / 1_000_000
        _validate_output(result)

    latency_ms = {
        "p50": float(np.quantile(durations, 0.50)),
        "p95": float(np.quantile(durations, 0.95)),
        "p99": float(np.quantile(durations, 0.99)),
        "mean": float(durations.mean()),
    }
    checks = {
        "cloud_run_job_identity": True,
        "single_first_attempt": True,
        "immutable_environment_image": True,
        "approved_model_checksum": True,
        "cpu_tensor_contract": True,
        "finite_outputs": True,
        "necessary_latency_limits": all(
            latency_ms[name] <= limit for name, limit in LATENCY_LIMITS_MS.items()
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "environment": deployment_environment,
        "cloud_run_job": job_name,
        "cloud_run_execution": execution_name,
        "image_uri": image_uri,
        "model_version": model_version,
        "model_sha256": model_sha256,
        "provider": "CPUExecutionProvider",
        "iterations": iterations,
        "warmup_iterations": warmup_iterations,
        "input_shape": INPUT_SHAPE,
        "output_shape": OUTPUT_SHAPE,
        "latency_ms": latency_ms,
        "limits_ms": LATENCY_LIMITS_MS,
        "checks": checks,
        "passed": all(checks.values()),
    }


def _validate_output(result: np.ndarray[Any, Any]) -> None:
    if result.shape != tuple(OUTPUT_SHAPE) or not np.isfinite(result).all():
        raise RuntimeError("ONNX Runtime returned an invalid benchmark output")


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{name} must be populated and trimmed")
    return value


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    report = benchmark_runtime_model()
    print(json.dumps(report, separators=(",", ":"), sort_keys=True), flush=True)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
