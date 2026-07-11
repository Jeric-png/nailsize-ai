from app.config import Settings
from app.runtime import load_runtime_models


def test_runtime_is_not_ready_from_version_string_alone(tmp_path) -> None:
    runtime = load_runtime_models(
        Settings(
            model_version="candidate-1",
            model_sha256="0" * 64,
            segmentation_boundary_error_px=0.5,
            model_path=str(tmp_path / "missing.onnx"),
            hand_landmarker_path=str(tmp_path / "missing.task"),
        )
    )
    assert not runtime.ready
    assert runtime.error_code == "MODEL_INITIALIZATION_FAILED"


def test_runtime_stays_unavailable_until_model_is_configured() -> None:
    runtime = load_runtime_models(Settings())
    assert not runtime.ready
    assert runtime.error_code == "MODEL_UNAVAILABLE"
