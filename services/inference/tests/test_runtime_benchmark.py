import hashlib
from pathlib import Path

import numpy as np
import onnx
import pytest
from onnx import TensorProto, helper

from app.runtime_benchmark import benchmark_runtime_model


def _write_model(path: Path, *, output_channels: int = 1) -> str:
    input_info = helper.make_tensor_value_info("image", TensorProto.FLOAT, [1, 3, 224, 160])
    output_info = helper.make_tensor_value_info(
        "mask_logits", TensorProto.FLOAT, [1, output_channels, 224, 160]
    )
    weights = np.full((output_channels, 3, 1, 1), 1 / 3, dtype=np.float32)
    initializer = helper.make_tensor(
        "weights", TensorProto.FLOAT, weights.shape, weights.flatten().tolist()
    )
    graph = helper.make_graph(
        [helper.make_node("Conv", ["image", "weights"], ["mask_logits"])],
        "runtime-benchmark-test",
        [input_info],
        [output_info],
        [initializer],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 18)])
    model.ir_version = 10
    onnx.save(model, path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _environment(path: Path, checksum: str) -> dict[str, str]:
    return {
        "DEPLOYMENT_ENVIRONMENT": "staging",
        "CLOUD_RUN_JOB": "nailsize-staging-onnx-benchmark",
        "CLOUD_RUN_EXECUTION": "nailsize-staging-onnx-benchmark-abc12",
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
        "CLOUD_RUN_TASK_COUNT": "1",
        "BENCHMARK_IMAGE_URI": (
            "us-central1-docker.pkg.dev/nailsize-staging/"
            "nailsize-staging-inference/inference@sha256:" + "a" * 64
        ),
        "MODEL_PATH": str(path),
        "MODEL_SHA256": checksum,
        "MODEL_VERSION": "nailsize-20260712",
    }


def test_benchmarks_exact_cloud_run_job_model_without_payload_data(tmp_path: Path) -> None:
    path = tmp_path / "model.onnx"
    checksum = _write_model(path)

    report = benchmark_runtime_model(environment=_environment(path, checksum))

    assert report["passed"] is True
    assert report["model_sha256"] == checksum
    assert report["provider"] == "CPUExecutionProvider"
    assert report["iterations"] == 200
    assert 0 <= report["latency_ms"]["p50"] <= report["latency_ms"]["p95"]
    assert "model.onnx" not in str(report)
    assert "project_id" not in str(report)


def test_rejects_nonfirst_task_checksum_and_tensor_drift(tmp_path: Path) -> None:
    path = tmp_path / "model.onnx"
    checksum = _write_model(path)
    environment = _environment(path, checksum)

    with pytest.raises(ValueError, match="first-attempt"):
        benchmark_runtime_model(environment=environment | {"CLOUD_RUN_TASK_ATTEMPT": "1"})
    with pytest.raises(ValueError, match="checksum"):
        benchmark_runtime_model(environment=environment | {"MODEL_SHA256": "0" * 64})

    invalid_path = tmp_path / "invalid.onnx"
    invalid_checksum = _write_model(invalid_path, output_channels=3)
    with pytest.raises(ValueError, match="tensor contract"):
        benchmark_runtime_model(environment=_environment(invalid_path, invalid_checksum))


@pytest.mark.parametrize(
    "overrides",
    [
        {"DEPLOYMENT_ENVIRONMENT": "development"},
        {"MODEL_VERSION": "synthetic-fixture"},
        {"CLOUD_RUN_TASK_COUNT": "2"},
        {"BENCHMARK_IMAGE_URI": "us-docker.pkg.dev/project/shared/image:latest"},
    ],
)
def test_rejects_unapproved_runtime_identity(tmp_path: Path, overrides: dict[str, str]) -> None:
    path = tmp_path / "model.onnx"
    checksum = _write_model(path)
    with pytest.raises(ValueError):
        benchmark_runtime_model(environment=_environment(path, checksum) | overrides)
