import copy

import pytest

from scripts.verify_cloud_run_benchmark import verify_cloud_run_benchmark

MODEL_VERSION = "nailsize-20260712"
MODEL_SHA256 = "b" * 64
IMAGE_URI = (
    "us-central1-docker.pkg.dev/nailsize-staging/"
    "nailsize-staging-inference/inference@sha256:" + "a" * 64
)
JOB = "nailsize-staging-onnx-benchmark"
EXECUTION = f"{JOB}-abc12"
FULL_JOB = f"projects/nailsize-staging/locations/us-central1/jobs/{JOB}"


def _evidence():
    sample = {
        "schema_version": "nailsize-cloud-run-onnx-benchmark-sample@1",
        "environment": "staging",
        "cloud_run_job": JOB,
        "cloud_run_execution": EXECUTION,
        "image_uri": IMAGE_URI,
        "model_version": MODEL_VERSION,
        "model_sha256": MODEL_SHA256,
        "provider": "CPUExecutionProvider",
        "iterations": 200,
        "warmup_iterations": 20,
        "input_shape": [1, 3, 224, 160],
        "output_shape": [1, 1, 224, 160],
        "latency_ms": {"p50": 80.0, "p95": 100.0, "p99": 120.0, "mean": 85.0},
        "limits_ms": {"p50": 2000.0, "p95": 5000.0, "p99": 10000.0},
        "checks": {
            "cloud_run_job_identity": True,
            "single_first_attempt": True,
            "immutable_environment_image": True,
            "approved_model_checksum": True,
            "cpu_tensor_contract": True,
            "finite_outputs": True,
            "necessary_latency_limits": True,
        },
        "passed": True,
    }
    return {
        "job": {
            "name": FULL_JOB,
            "template": {
                "parallelism": 1,
                "taskCount": 1,
                "template": {
                    "maxRetries": 0,
                    "timeout": "300s",
                    "executionEnvironment": "EXECUTION_ENVIRONMENT_GEN2",
                    "containers": [
                        {
                            "image": IMAGE_URI,
                            "command": ["python"],
                            "args": ["-m", "app.runtime_benchmark"],
                            "resources": {"limits": {"cpu": "2", "memory": "4Gi"}},
                            "env": [
                                {"name": "BENCHMARK_IMAGE_URI", "value": IMAGE_URI},
                                {"name": "DEPLOYMENT_ENVIRONMENT", "value": "staging"},
                                {"name": "MODEL_PATH", "value": "models/nail-segmentation.onnx"},
                                {"name": "MODEL_SHA256", "value": MODEL_SHA256},
                                {"name": "MODEL_VERSION", "value": MODEL_VERSION},
                            ],
                        }
                    ],
                },
            },
        },
        "execution": {
            "name": f"{FULL_JOB}/executions/{EXECUTION}",
            "job": FULL_JOB,
            "parallelism": 1,
            "taskCount": 1,
            "succeededCount": 1,
            "failedCount": 0,
            "cancelledCount": 0,
            "retriedCount": 0,
            "completionTime": "2026-07-12T02:00:00Z",
        },
        "log_entries": [
            {
                "resource": {"type": "cloud_run_job", "labels": {"job_name": JOB}},
                "labels": {"execution_name": EXECUTION},
                "jsonPayload": sample,
            }
        ],
    }


def _verify(evidence):
    return verify_cloud_run_benchmark(
        **evidence,
        expected_environment="staging",
        expected_image_uri=IMAGE_URI,
        expected_model_version=MODEL_VERSION,
        expected_model_sha256=MODEL_SHA256,
    )


def test_verifies_exact_job_execution_and_structured_sample() -> None:
    report = _verify(_evidence())

    assert report["passed"] is True
    assert report["runtime_contract"]["cpu"] == "2"
    assert report["runtime_contract"]["memory"] == "4Gi"
    assert report["cloud_run_execution"] == EXECUTION
    assert report["latency_ms"]["p95"] == 100.0


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("job", "template", "taskCount"), 2),
        (("job", "template", "template", "maxRetries"), 1),
        (("job", "template", "template", "containers", 0, "image"), "mutable:latest"),
        (("execution", "retriedCount"), 1),
        (("execution", "succeededCount"), 0),
        (("log_entries", 0, "jsonPayload", "model_sha256"), "c" * 64),
        (("log_entries", 0, "jsonPayload", "latency_ms", "p95"), 5001.0),
        (("log_entries", 0, "jsonPayload", "checks", "finite_outputs"), False),
    ],
)
def test_rejects_configuration_execution_and_sample_drift(path, value) -> None:
    evidence = copy.deepcopy(_evidence())
    target = evidence
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValueError):
        _verify(evidence)


def test_rejects_duplicate_or_wrong_execution_logs() -> None:
    duplicate = _evidence()
    duplicate["log_entries"].append(copy.deepcopy(duplicate["log_entries"][0]))
    with pytest.raises(ValueError, match="exactly one"):
        _verify(duplicate)

    wrong = _evidence()
    wrong["log_entries"][0]["labels"]["execution_name"] = "different"
    with pytest.raises(ValueError, match="exactly one"):
        _verify(wrong)
