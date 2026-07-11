from pathlib import Path

import pytest

onnx = pytest.importorskip("onnx")
torch = pytest.importorskip("torch")
pytest.importorskip("torchvision")
nn = torch.nn

from nailsize_ml.modeling import (  # noqa: E402
    INPUT_HEIGHT,
    INPUT_WIDTH,
    build_deeplab_mobilenet,
    combined_segmentation_loss,
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
    checksum = export_verified_onnx(
        TinySegmentationModel(), path, model_version="synthetic-test-model"
    )
    assert len(checksum) == 64
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
    with pytest.raises(ValueError, match="output"):
        export_verified_onnx(
            nn.Identity(), tmp_path / "invalid.onnx", model_version="synthetic-test-model"
        )
    with pytest.raises(ValueError, match="version"):
        export_verified_onnx(TinySegmentationModel(), tmp_path / "invalid.onnx", model_version="")
