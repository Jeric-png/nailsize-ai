import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

INPUT_HEIGHT = 224
INPUT_WIDTH = 160


@dataclass(frozen=True)
class OnnxExportReport:
    model_sha256: str
    model_version: str
    parity_max_abs_error: float
    parity_tolerance: float
    input_shape: tuple[int, int, int, int]
    output_shape: tuple[int, int, int, int]
    provider: str


@dataclass(frozen=True)
class SelectedCheckpointExportReport:
    schema_version: str
    architecture: str
    checkpoint_sha256: str
    model_sha256: str
    model_version: str
    training_examples: int
    training_epochs: int
    final_training_loss: float
    parity_max_abs_error: float
    parity_tolerance: float
    input_shape: tuple[int, int, int, int]
    output_shape: tuple[int, int, int, int]
    provider: str
    checkpoint_torch_version: str


def build_deeplab_mobilenet(*, pretrained_backbone: bool = True) -> Any:
    """Build the one-channel DeepLabV3-MobileNetV3 baseline."""
    try:
        from torch import nn
        from torchvision.models import MobileNet_V3_Large_Weights
        from torchvision.models.segmentation import deeplabv3_mobilenet_v3_large
    except ImportError as error:
        raise RuntimeError("Install nailsize-ml-tooling[training] to build the model") from error

    backbone_weights = MobileNet_V3_Large_Weights.DEFAULT if pretrained_backbone else None
    model = deeplabv3_mobilenet_v3_large(
        weights=None,
        weights_backbone=backbone_weights,
        num_classes=1,
        aux_loss=False,
    )

    class LogitsOnly(nn.Module):
        def __init__(self, segmentation_model: Any) -> None:
            super().__init__()
            self.segmentation_model = segmentation_model

        def forward(self, image):
            return self.segmentation_model(image)["out"]

    return LogitsOnly(model)


def combined_segmentation_loss(logits: Any, targets: Any) -> Any:
    try:
        import torch
        from torch.nn import functional as functional
    except ImportError as error:
        raise RuntimeError("Install nailsize-ml-tooling[training] to compute model loss") from error
    if logits.shape != targets.shape or logits.ndim != 4 or logits.shape[1] != 1:
        raise ValueError("Logits and targets must share shape [batch, 1, height, width]")
    if not torch.isfinite(logits).all() or not torch.isfinite(targets).all():
        raise ValueError("Logits and targets must be finite")
    if torch.any((targets < 0) | (targets > 1)):
        raise ValueError("Segmentation targets must be in [0, 1]")

    binary_cross_entropy = functional.binary_cross_entropy_with_logits(logits, targets)
    probabilities = torch.sigmoid(logits)
    intersection = (probabilities * targets).sum(dim=(1, 2, 3))
    denominator = probabilities.sum(dim=(1, 2, 3)) + targets.sum(dim=(1, 2, 3))
    dice_loss = 1 - ((2 * intersection + 1) / (denominator + 1)).mean()
    return binary_cross_entropy + dice_loss


def export_verified_onnx(
    model: Any,
    destination: str | Path,
    *,
    model_version: str,
    parity_atol: float = 1e-4,
) -> OnnxExportReport:
    try:
        import onnx
        import onnxruntime as ort
        import torch
    except ImportError as error:
        raise RuntimeError("Install nailsize-ml-tooling[training] to export the model") from error
    if not model_version.strip() or not math.isfinite(parity_atol) or parity_atol <= 0:
        raise ValueError("Model version and a positive parity tolerance are required")

    path = Path(destination)
    if path.exists():
        raise ValueError("ONNX destination must not already exist")
    path.parent.mkdir(parents=True, exist_ok=True)
    model.eval()
    torch.manual_seed(0)
    example = torch.rand((1, 3, INPUT_HEIGHT, INPUT_WIDTH), dtype=torch.float32)
    with torch.no_grad():
        native = model(example).detach().cpu().numpy()
    if native.shape != (1, 1, INPUT_HEIGHT, INPUT_WIDTH) or not np.isfinite(native).all():
        raise ValueError("Model output does not satisfy the inference tensor contract")

    temporary_path = _temporary_path(path, suffix=".onnx")
    try:
        program = torch.onnx.export(
            model,
            (example,),
            input_names=["image"],
            output_names=["mask_logits"],
            dynamo=True,
            external_data=False,
        )
        program.save(temporary_path, external_data=False)
        graph = onnx.load(temporary_path)
        del graph.metadata_props[:]
        metadata = graph.metadata_props.add()
        metadata.key = "nailsize.model_version"
        metadata.value = model_version
        onnx.checker.check_model(graph)
        onnx.save(graph, temporary_path)

        session = ort.InferenceSession(temporary_path, providers=["CPUExecutionProvider"])
        exported = session.run(["mask_logits"], {"image": example.numpy()})[0]
        if exported.shape != native.shape or not np.isfinite(exported).all():
            raise RuntimeError("ONNX output does not satisfy the inference tensor contract")
        maximum_error = float(np.max(np.abs(exported - native)))
        if maximum_error > parity_atol:
            raise RuntimeError(f"ONNX parity error {maximum_error} exceeds {parity_atol}")
        checksum = hashlib.sha256(temporary_path.read_bytes()).hexdigest()
        provider = session.get_providers()[0]
        del session
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return OnnxExportReport(
        model_sha256=checksum,
        model_version=model_version,
        parity_max_abs_error=maximum_error,
        parity_tolerance=parity_atol,
        input_shape=(1, 3, INPUT_HEIGHT, INPUT_WIDTH),
        output_shape=(1, 1, INPUT_HEIGHT, INPUT_WIDTH),
        provider=provider,
    )


def export_selected_checkpoint(
    checkpoint_path: str | Path,
    destination: str | Path,
    report_path: str | Path,
    *,
    expected_checkpoint_sha256: str,
    expected_model_version: str,
    parity_atol: float = 1e-4,
) -> SelectedCheckpointExportReport:
    try:
        import torch
    except ImportError as error:
        raise RuntimeError(
            "Install nailsize-ml-tooling[training] to export a checkpoint"
        ) from error

    checkpoint_file = Path(checkpoint_path)
    destination_file = Path(destination)
    report_file = Path(report_path)
    if not checkpoint_file.is_file():
        raise ValueError("Selected checkpoint does not exist")
    if destination_file.exists() or report_file.exists():
        raise ValueError("ONNX and report destinations must not already exist")
    resolved_paths = {
        checkpoint_file.resolve(),
        destination_file.resolve(),
        report_file.resolve(),
    }
    if len(resolved_paths) != 3:
        raise ValueError("Checkpoint, ONNX, and report paths must be distinct")
    if not _valid_sha256(expected_checkpoint_sha256):
        raise ValueError("Expected checkpoint SHA-256 must be lowercase hexadecimal")
    actual_checkpoint_sha256 = _sha256(checkpoint_file)
    if actual_checkpoint_sha256 != expected_checkpoint_sha256:
        raise ValueError("Selected checkpoint checksum does not match approval")

    try:
        checkpoint = torch.load(checkpoint_file, map_location="cpu", weights_only=True)
    except Exception as error:
        raise ValueError("Selected checkpoint could not be safely loaded") from error
    if not isinstance(checkpoint, dict):
        raise ValueError("Selected checkpoint must contain a mapping")
    config = checkpoint.get("config")
    state = checkpoint.get("model_state_dict")
    losses = checkpoint.get("losses")
    training_examples = checkpoint.get("training_examples")
    checkpoint_torch_version = checkpoint.get("torch_version")
    if not isinstance(config, dict) or config.get("model_version") != expected_model_version:
        raise ValueError("Checkpoint model version does not match the selected version")
    epochs = config.get("epochs")
    if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs <= 0:
        raise ValueError("Checkpoint training epoch count is invalid")
    if (
        isinstance(training_examples, bool)
        or not isinstance(training_examples, int)
        or training_examples <= 0
    ):
        raise ValueError("Checkpoint training example count is invalid")
    if not isinstance(losses, (list, tuple)) or len(losses) != epochs:
        raise ValueError("Checkpoint loss history does not match its training epochs")
    numeric_losses = tuple(_finite_number(value, "training loss") for value in losses)
    if any(loss < 0 for loss in numeric_losses):
        raise ValueError("Checkpoint training loss must not be negative")
    if not isinstance(state, dict) or not state:
        raise ValueError("Checkpoint model state is missing")
    if not isinstance(checkpoint_torch_version, str) or not checkpoint_torch_version.strip():
        raise ValueError("Checkpoint PyTorch version is missing")

    model = build_deeplab_mobilenet(pretrained_backbone=False)
    try:
        model.load_state_dict(state, strict=True)
    except (RuntimeError, TypeError, ValueError) as error:
        raise ValueError("Checkpoint state does not match DeepLabV3-MobileNetV3") from error
    exported = export_verified_onnx(
        model,
        destination_file,
        model_version=expected_model_version,
        parity_atol=parity_atol,
    )
    report = SelectedCheckpointExportReport(
        schema_version="nailsize-selected-checkpoint-export@1",
        architecture="deeplabv3_mobilenet_v3_large",
        checkpoint_sha256=actual_checkpoint_sha256,
        model_sha256=exported.model_sha256,
        model_version=expected_model_version,
        training_examples=training_examples,
        training_epochs=epochs,
        final_training_loss=numeric_losses[-1],
        parity_max_abs_error=exported.parity_max_abs_error,
        parity_tolerance=exported.parity_tolerance,
        input_shape=exported.input_shape,
        output_shape=exported.output_shape,
        provider=exported.provider,
        checkpoint_torch_version=checkpoint_torch_version,
    )
    try:
        _write_json_atomic(report_file, asdict(report))
    except Exception:
        destination_file.unlink(missing_ok=True)
        raise
    return report


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be finite")
    return float(value)


def _temporary_path(destination: Path, *, suffix: str) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=suffix,
    )
    os.close(descriptor)
    return Path(temporary)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary_path = _temporary_path(path, suffix=".json")
    try:
        temporary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
