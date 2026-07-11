import hashlib

import numpy as np
import onnx
import pytest
from onnx import TensorProto, helper

from app.segmentation import (
    INPUT_HEIGHT,
    INPUT_WIDTH,
    ModelLoadError,
    NailSegmentationModel,
)


def build_test_model(path, *, version: str = "test-model-1") -> str:
    input_info = helper.make_tensor_value_info(
        "image", TensorProto.FLOAT, [1, 3, INPUT_HEIGHT, INPUT_WIDTH]
    )
    output_info = helper.make_tensor_value_info(
        "logits", TensorProto.FLOAT, [1, 1, INPUT_HEIGHT, INPUT_WIDTH]
    )
    node = helper.make_node("ReduceMean", ["image"], ["logits"], axes=[1], keepdims=1)
    graph = helper.make_graph([node], "test-segmentation", [input_info], [output_info])
    model = helper.make_model(
        graph,
        producer_name="nailsize-tests",
        opset_imports=[helper.make_operatorsetid("", 17)],
    )
    model.metadata_props.add(key="nailsize.model_version", value=version)
    onnx.save(model, path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_loads_verified_model_warms_up_and_segments(tmp_path) -> None:
    path = tmp_path / "nail.onnx"
    checksum = build_test_model(path)
    model = NailSegmentationModel(path, sha256=checksum, model_version="test-model-1")

    result = model.segment(np.full((INPUT_HEIGHT, INPUT_WIDTH, 3), 255, dtype=np.uint8))

    assert result.mask.shape == (INPUT_HEIGHT, INPUT_WIDTH)
    assert result.mask.dtype == np.uint8
    assert result.mask.all()
    assert result.confidence > 0.9


def test_rejects_missing_checksum_mismatch_and_version_mismatch(tmp_path) -> None:
    missing = tmp_path / "missing.onnx"
    with pytest.raises(ModelLoadError, match="not found"):
        NailSegmentationModel(missing, sha256="0" * 64, model_version="test-model-1")

    path = tmp_path / "nail.onnx"
    checksum = build_test_model(path)
    with pytest.raises(ModelLoadError, match="checksum mismatch"):
        NailSegmentationModel(path, sha256="0" * 64, model_version="test-model-1")
    with pytest.raises(ModelLoadError, match="version metadata"):
        NailSegmentationModel(path, sha256=checksum, model_version="other-version")


def test_rejects_wrong_crop_contract(tmp_path) -> None:
    path = tmp_path / "nail.onnx"
    checksum = build_test_model(path)
    model = NailSegmentationModel(path, sha256=checksum, model_version="test-model-1")
    with pytest.raises(ValueError, match="Expected uint8 RGB"):
        model.segment(np.zeros((32, 32, 3), dtype=np.uint8))
