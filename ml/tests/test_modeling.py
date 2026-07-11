import hashlib
import json
from pathlib import Path

import pytest

onnx = pytest.importorskip("onnx")
torch = pytest.importorskip("torch")
pytest.importorskip("torchvision")
nn = torch.nn

import nailsize_ml.modeling as modeling  # noqa: E402
from nailsize_ml.modeling import (  # noqa: E402
    INPUT_HEIGHT,
    INPUT_WIDTH,
    OnnxExportReport,
    build_deeplab_mobilenet,
    combined_segmentation_loss,
    export_selected_checkpoint,
    export_verified_onnx,
)


def test_deeplab_mobilenet_emits_one_logit_channel() -> None:
    model = build_deeplab_mobilenet(pretrained_backbone=False).eval()
    with torch.no_grad():
        output = model(torch.zeros((1, 3, 64, 64)))
    assert output.shape == (1, 1, 64, 64)


def test_combined_loss_rewards_correct_logits_and_rejects_invalid_targets() -> None:
    targets = torch.tensor([[[[0.0, 1.0], [1.0, 0.0]]]])
    correct = torch.tensor([[[[-8.0, 8.0], [8.0, -8.0]]]])
    incorrect = -correct
    assert combined_segmentation_loss(correct, targets) < combined_segmentation_loss(
        incorrect, targets
    )
    with pytest.raises(ValueError):
        combined_segmentation_loss(correct, targets + 2)


class TinySegmentationModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.projection = nn.Conv2d(3, 1, kernel_size=1)

    def forward(self, image):
        return self.projection(image)


def test_exports_static_contract_with_metadata_and_runtime_parity(tmp_path: Path) -> None:
    path = tmp_path / "model.onnx"
    report = export_verified_onnx(
        TinySegmentationModel(), path, model_version="synthetic-test-model"
    )
    assert len(report.model_sha256) == 64
    assert report.parity_max_abs_error <= report.parity_tolerance
    assert report.provider == "CPUExecutionProvider"
    assert report.input_shape == (1, 3, INPUT_HEIGHT, INPUT_WIDTH)
    assert report.output_shape == (1, 1, INPUT_HEIGHT, INPUT_WIDTH)
    graph = onnx.load(path)
    assert {item.key: item.value for item in graph.metadata_props} == {
        "nailsize.model_version": "synthetic-test-model"
    }
    assert [
        dimension.dim_value for dimension in graph.graph.input[0].type.tensor_type.shape.dim
    ] == [
        1,
        3,
        INPUT_HEIGHT,
        INPUT_WIDTH,
    ]
    assert [
        dimension.dim_value for dimension in graph.graph.output[0].type.tensor_type.shape.dim
    ] == [1, 1, INPUT_HEIGHT, INPUT_WIDTH]


def test_export_rejects_invalid_contract(tmp_path: Path) -> None:
    destination = tmp_path / "invalid.onnx"
    with pytest.raises(ValueError, match="output"):
        export_verified_onnx(nn.Identity(), destination, model_version="synthetic-test-model")
    assert not destination.exists()
    with pytest.raises(ValueError, match="version"):
        export_verified_onnx(TinySegmentationModel(), destination, model_version="")
    with pytest.raises(ValueError, match="tolerance"):
        export_verified_onnx(
            TinySegmentationModel(),
            destination,
            model_version="synthetic-test-model",
            parity_atol=float("nan"),
        )


def _write_checkpoint(path: Path, model: nn.Module, *, model_version: str = "candidate-1") -> str:
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "config": {"model_version": model_version, "epochs": 2},
            "training_examples": 24,
            "losses": (1.2, 0.8),
            "torch_version": str(torch.__version__),
        },
        path,
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_exports_checksum_selected_checkpoint_and_machine_readable_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    source_model = TinySegmentationModel()
    checkpoint = tmp_path / "selected.pt"
    checkpoint_sha256 = _write_checkpoint(checkpoint, source_model)
    monkeypatch.setattr(
        modeling,
        "build_deeplab_mobilenet",
        lambda *, pretrained_backbone: TinySegmentationModel(),
    )
    onnx_path = tmp_path / "candidate.onnx"
    report_path = tmp_path / "candidate-export.json"

    report = export_selected_checkpoint(
        checkpoint,
        onnx_path,
        report_path,
        expected_checkpoint_sha256=checkpoint_sha256,
        expected_model_version="candidate-1",
    )

    assert onnx_path.is_file()
    assert report.checkpoint_sha256 == checkpoint_sha256
    assert report.model_sha256 == hashlib.sha256(onnx_path.read_bytes()).hexdigest()
    assert report.model_version == "candidate-1"
    assert report.training_examples == 24
    assert report.training_epochs == 2
    assert report.final_training_loss == 0.8
    assert report.parity_max_abs_error <= 1e-4
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "nailsize-selected-checkpoint-export@1"
    assert payload["architecture"] == "deeplabv3_mobilenet_v3_large"
    assert payload["input_shape"] == [1, 3, INPUT_HEIGHT, INPUT_WIDTH]
    assert payload["output_shape"] == [1, 1, INPUT_HEIGHT, INPUT_WIDTH]


@pytest.mark.parametrize(
    ("checksum", "version", "message"),
    [
        ("0" * 64, "candidate-1", "checksum"),
        (None, "candidate-2", "version"),
    ],
)
def test_selected_checkpoint_rejects_unapproved_identity(
    tmp_path: Path, monkeypatch, checksum: str | None, version: str, message: str
) -> None:
    checkpoint = tmp_path / "selected.pt"
    actual = _write_checkpoint(checkpoint, TinySegmentationModel())
    monkeypatch.setattr(
        modeling,
        "build_deeplab_mobilenet",
        lambda *, pretrained_backbone: TinySegmentationModel(),
    )

    with pytest.raises(ValueError, match=message):
        export_selected_checkpoint(
            checkpoint,
            tmp_path / "candidate.onnx",
            tmp_path / "candidate-export.json",
            expected_checkpoint_sha256=actual if checksum is None else checksum,
            expected_model_version=version,
        )

    assert not (tmp_path / "candidate.onnx").exists()
    assert not (tmp_path / "candidate-export.json").exists()


def test_selected_checkpoint_removes_onnx_when_evidence_write_fails(
    tmp_path: Path, monkeypatch
) -> None:
    checkpoint = tmp_path / "selected.pt"
    checkpoint_sha256 = _write_checkpoint(checkpoint, TinySegmentationModel())
    monkeypatch.setattr(
        modeling,
        "build_deeplab_mobilenet",
        lambda *, pretrained_backbone: TinySegmentationModel(),
    )

    def fake_export(_model, destination, **_kwargs):
        Path(destination).write_bytes(b"verified-onnx")
        return OnnxExportReport(
            model_sha256=hashlib.sha256(b"verified-onnx").hexdigest(),
            model_version="candidate-1",
            parity_max_abs_error=0.0,
            parity_tolerance=1e-4,
            input_shape=(1, 3, INPUT_HEIGHT, INPUT_WIDTH),
            output_shape=(1, 1, INPUT_HEIGHT, INPUT_WIDTH),
            provider="CPUExecutionProvider",
        )

    monkeypatch.setattr(modeling, "export_verified_onnx", fake_export)
    monkeypatch.setattr(
        modeling,
        "_write_json_atomic",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk failure")),
    )
    onnx_path = tmp_path / "candidate.onnx"

    with pytest.raises(OSError, match="disk failure"):
        export_selected_checkpoint(
            checkpoint,
            onnx_path,
            tmp_path / "candidate-export.json",
            expected_checkpoint_sha256=checkpoint_sha256,
            expected_model_version="candidate-1",
        )

    assert not onnx_path.exists()
