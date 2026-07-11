import pytest
from test_segmentation import build_test_model

from app.segmentation import ModelLoadError
from scripts.verify_runtime_model import verify_runtime_model


def test_verifies_release_model_with_production_cpu_runtime(tmp_path) -> None:
    path = tmp_path / "nail-segmentation.onnx"
    checksum = build_test_model(path, version="release-1")

    report = verify_runtime_model(path, sha256=checksum, model_version="release-1")

    assert report == {
        "schema_version": "nailsize-runtime-model-verification@1",
        "model_version": "release-1",
        "model_sha256": checksum,
        "runtime_provider": "CPUExecutionProvider",
        "status": "ready",
    }


def test_runtime_verification_rejects_checksum_or_version_mismatch(tmp_path) -> None:
    path = tmp_path / "nail-segmentation.onnx"
    checksum = build_test_model(path, version="release-1")

    with pytest.raises(ModelLoadError, match="checksum mismatch"):
        verify_runtime_model(path, sha256="0" * 64, model_version="release-1")
    with pytest.raises(ModelLoadError, match="version metadata"):
        verify_runtime_model(path, sha256=checksum, model_version="release-2")
