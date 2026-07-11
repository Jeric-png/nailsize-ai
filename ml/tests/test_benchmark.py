from pathlib import Path

import numpy as np
import onnx
import pytest
from onnx import TensorProto, helper

pytest.importorskip("onnxruntime")

from nailsize_ml.benchmark import benchmark_onnx  # noqa: E402
from nailsize_ml.modeling import INPUT_HEIGHT, INPUT_WIDTH  # noqa: E402


def write_identity_model(path: Path, *, valid_output: bool = True) -> None:
    input_info = helper.make_tensor_value_info(
        "image", TensorProto.FLOAT, [1, 3, INPUT_HEIGHT, INPUT_WIDTH]
    )
    output_channels = 1 if valid_output else 3
    output_info = helper.make_tensor_value_info(
        "mask_logits", TensorProto.FLOAT, [1, output_channels, INPUT_HEIGHT, INPUT_WIDTH]
    )
    weights = np.full((output_channels, 3, 1, 1), 1 / 3, dtype=np.float32)
    initializer = helper.make_tensor(
        "weights", TensorProto.FLOAT, weights.shape, weights.flatten().tolist()
    )
    node = helper.make_node("Conv", ["image", "weights"], ["mask_logits"])
    graph = helper.make_graph([node], "benchmark-test", [input_info], [output_info], [initializer])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 18)])
    model.ir_version = 10
    onnx.save(model, path)


def test_benchmarks_fixed_shape_cpu_model(tmp_path: Path) -> None:
    path = tmp_path / "model.onnx"
    write_identity_model(path)
    report = benchmark_onnx(path, iterations=3, warmup_iterations=1)
    assert len(report.model_sha256) == 64
    assert report.provider == "CPUExecutionProvider"
    assert report.iterations == 3
    assert 0 <= report.p50_ms <= report.p95_ms <= report.p99_ms
    assert report.mean_ms >= 0
    assert report.machine


def test_rejects_invalid_model_contract_and_iteration_counts(tmp_path: Path) -> None:
    path = tmp_path / "invalid.onnx"
    write_identity_model(path, valid_output=False)
    with pytest.raises(ValueError, match="output"):
        benchmark_onnx(path, iterations=1)
    with pytest.raises(ValueError, match="iteration"):
        benchmark_onnx(path, iterations=0)
