import argparse
import json
import math
from pathlib import Path
from typing import Any

from app.runtime_benchmark import (
    INPUT_SHAPE,
    LATENCY_LIMITS_MS,
    MIN_ITERATIONS,
    MIN_WARMUP_ITERATIONS,
    OUTPUT_SHAPE,
)
from app.runtime_benchmark import (
    SCHEMA_VERSION as SAMPLE_SCHEMA,
)

REPORT_SCHEMA = "nailsize-cloud-run-onnx-benchmark@1"


def verify_cloud_run_benchmark(
    *,
    job: dict[str, Any],
    execution: dict[str, Any],
    log_entries: list[Any],
    expected_environment: str,
    expected_image_uri: str,
    expected_model_version: str,
    expected_model_sha256: str,
) -> dict[str, Any]:
    if expected_environment not in {"staging", "production"}:
        raise ValueError("Benchmark environment must be staging or production")
    job_name = f"nailsize-{expected_environment}-onnx-benchmark"
    full_job_name = job.get("name")
    if not isinstance(full_job_name, str) or not full_job_name.endswith(f"/jobs/{job_name}"):
        raise ValueError("Benchmark job name does not match the deployment environment")
    template = job.get("template")
    if not isinstance(template, dict):
        raise ValueError("Benchmark job template is missing")
    task = template.get("template")
    containers = task.get("containers") if isinstance(task, dict) else None
    if (
        template.get("parallelism") != 1
        or template.get("taskCount") != 1
        or not isinstance(task, dict)
        or task.get("maxRetries") != 0
        or task.get("timeout") != "300s"
        or task.get("executionEnvironment") != "EXECUTION_ENVIRONMENT_GEN2"
        or not isinstance(containers, list)
        or len(containers) != 1
    ):
        raise ValueError("Benchmark job must use one no-retry Gen2 task with a five-minute timeout")
    container = containers[0]
    resources = container.get("resources") if isinstance(container, dict) else None
    limits = resources.get("limits") if isinstance(resources, dict) else None
    if (
        not isinstance(container, dict)
        or container.get("image") != expected_image_uri
        or container.get("command") != ["python"]
        or container.get("args") != ["-m", "app.runtime_benchmark"]
        or limits != {"cpu": "2", "memory": "4Gi"}
    ):
        raise ValueError(
            "Benchmark job does not use the exact image, command, CPU, and memory contract"
        )
    environment = _environment_map(container.get("env"))
    expected_environment_values = {
        "BENCHMARK_IMAGE_URI": expected_image_uri,
        "DEPLOYMENT_ENVIRONMENT": expected_environment,
        "MODEL_PATH": "models/nail-segmentation.onnx",
        "MODEL_SHA256": expected_model_sha256,
        "MODEL_VERSION": expected_model_version,
    }
    if environment != expected_environment_values:
        raise ValueError("Benchmark job environment does not match the selected model and image")

    execution_name = execution.get("name")
    if (
        not isinstance(execution_name, str)
        or not execution_name.startswith(f"{full_job_name}/executions/{job_name}-")
        or execution.get("job") != full_job_name
        or execution.get("parallelism") != 1
        or execution.get("taskCount") != 1
        or execution.get("succeededCount") != 1
        or execution.get("failedCount", 0) != 0
        or execution.get("cancelledCount", 0) != 0
        or execution.get("retriedCount", 0) != 0
        or not isinstance(execution.get("completionTime"), str)
        or not execution["completionTime"]
    ):
        raise ValueError("Benchmark execution is not one completed first-attempt task")
    short_execution_name = execution_name.rsplit("/", 1)[-1]
    sample = _extract_sample(log_entries, job_name, short_execution_name)
    _validate_sample(
        sample,
        expected_environment=expected_environment,
        expected_job_name=job_name,
        expected_execution_name=short_execution_name,
        expected_image_uri=expected_image_uri,
        expected_model_version=expected_model_version,
        expected_model_sha256=expected_model_sha256,
    )
    return {
        "schema_version": REPORT_SCHEMA,
        "environment": expected_environment,
        "cloud_run_job": job_name,
        "cloud_run_execution": short_execution_name,
        "image_uri": expected_image_uri,
        "model_version": expected_model_version,
        "model_sha256": expected_model_sha256,
        "provider": "CPUExecutionProvider",
        "iterations": sample["iterations"],
        "warmup_iterations": sample["warmup_iterations"],
        "input_shape": INPUT_SHAPE,
        "output_shape": OUTPUT_SHAPE,
        "runtime_contract": {
            "cpu": "2",
            "memory": "4Gi",
            "execution_environment": "gen2",
            "task_count": 1,
            "parallelism": 1,
            "max_retries": 0,
            "timeout_seconds": 300,
        },
        "latency_ms": sample["latency_ms"],
        "limits_ms": LATENCY_LIMITS_MS,
        "checks": {
            "immutable_image": True,
            "selected_model": True,
            "cloud_run_job_contract": True,
            "successful_single_task": True,
            "structured_sample_linked": True,
            "cpu_tensor_contract": True,
            "finite_outputs": True,
            "necessary_latency_limits": True,
        },
        "passed": True,
    }


def _environment_map(value: Any) -> dict[str, str]:
    if not isinstance(value, list):
        raise ValueError("Benchmark job environment is missing")
    result: dict[str, str] = {}
    for item in value:
        if (
            not isinstance(item, dict)
            or set(item) != {"name", "value"}
            or not isinstance(item.get("name"), str)
            or not isinstance(item.get("value"), str)
            or item["name"] in result
        ):
            raise ValueError("Benchmark job environment must contain exact plain values")
        result[item["name"]] = item["value"]
    return result


def _extract_sample(entries: list[Any], job_name: str, execution_name: str) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        payload = entry.get("jsonPayload")
        resource = entry.get("resource")
        labels = entry.get("labels")
        if (
            isinstance(payload, dict)
            and payload.get("schema_version") == SAMPLE_SCHEMA
            and isinstance(resource, dict)
            and resource.get("type") == "cloud_run_job"
            and isinstance(resource.get("labels"), dict)
            and resource["labels"].get("job_name") == job_name
            and isinstance(labels, dict)
            and labels.get("execution_name") == execution_name
        ):
            candidates.append(payload)
    if len(candidates) != 1:
        raise ValueError("Expected exactly one execution-scoped structured benchmark sample")
    return candidates[0]


def _validate_sample(
    sample: dict[str, Any],
    *,
    expected_environment: str,
    expected_job_name: str,
    expected_execution_name: str,
    expected_image_uri: str,
    expected_model_version: str,
    expected_model_sha256: str,
) -> None:
    expected_fields = {
        "schema_version",
        "environment",
        "cloud_run_job",
        "cloud_run_execution",
        "image_uri",
        "model_version",
        "model_sha256",
        "provider",
        "iterations",
        "warmup_iterations",
        "input_shape",
        "output_shape",
        "latency_ms",
        "limits_ms",
        "checks",
        "passed",
    }
    if set(sample) != expected_fields or sample.get("passed") is not True:
        raise ValueError("Benchmark sample does not match the exact passing contract")
    if (
        sample.get("environment") != expected_environment
        or sample.get("cloud_run_job") != expected_job_name
        or sample.get("cloud_run_execution") != expected_execution_name
        or sample.get("image_uri") != expected_image_uri
        or sample.get("model_version") != expected_model_version
        or sample.get("model_sha256") != expected_model_sha256
        or sample.get("provider") != "CPUExecutionProvider"
        or sample.get("input_shape") != INPUT_SHAPE
        or sample.get("output_shape") != OUTPUT_SHAPE
        or sample.get("limits_ms") != LATENCY_LIMITS_MS
    ):
        raise ValueError("Benchmark sample identity or tensor contract does not match deployment")
    if (
        not isinstance(sample.get("iterations"), int)
        or sample["iterations"] < MIN_ITERATIONS
        or not isinstance(sample.get("warmup_iterations"), int)
        or sample["warmup_iterations"] < MIN_WARMUP_ITERATIONS
    ):
        raise ValueError("Benchmark sample does not contain enough measured iterations")
    expected_checks = {
        "cloud_run_job_identity",
        "single_first_attempt",
        "immutable_environment_image",
        "approved_model_checksum",
        "cpu_tensor_contract",
        "finite_outputs",
        "necessary_latency_limits",
    }
    checks = sample.get("checks")
    if (
        not isinstance(checks, dict)
        or set(checks) != expected_checks
        or any(value is not True for value in checks.values())
    ):
        raise ValueError("Benchmark sample checks must all pass")
    latency = sample.get("latency_ms")
    if not isinstance(latency, dict) or set(latency) != {"p50", "p95", "p99", "mean"}:
        raise ValueError("Benchmark latency fields do not match the contract")
    values = {name: _finite_nonnegative(value, name) for name, value in latency.items()}
    if not values["p50"] <= values["p95"] <= values["p99"]:
        raise ValueError("Benchmark latency quantiles are not ordered")
    if any(values[name] > limit for name, limit in LATENCY_LIMITS_MS.items()):
        raise ValueError("Benchmark sample exceeds a necessary end-to-end latency limit")


def _finite_nonnegative(value: Any, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"Benchmark latency must be finite and nonnegative: {name}")
    return float(value)


def _read_object(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Benchmark evidence must be an object: {path.name}")
    return payload


def _read_array(path: Path) -> list[Any]:
    payload = _read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Benchmark evidence must be an array: {path.name}")
    return payload


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read benchmark evidence: {path.name}") from error


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify an exact Cloud Run ONNX benchmark")
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--execution", required=True, type=Path)
    parser.add_argument("--logs", required=True, type=Path)
    parser.add_argument("--expected-environment", required=True)
    parser.add_argument("--expected-image-uri", required=True)
    parser.add_argument("--expected-model-version", required=True)
    parser.add_argument("--expected-model-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        report = verify_cloud_run_benchmark(
            job=_read_object(arguments.job),
            execution=_read_object(arguments.execution),
            log_entries=_read_array(arguments.logs),
            expected_environment=arguments.expected_environment,
            expected_image_uri=arguments.expected_image_uri,
            expected_model_version=arguments.expected_model_version,
            expected_model_sha256=arguments.expected_model_sha256,
        )
    except ValueError as error:
        parser.error(str(error))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
