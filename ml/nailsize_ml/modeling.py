import hashlib
from pathlib import Path
from typing import Any

import numpy as np

INPUT_HEIGHT = 224
INPUT_WIDTH = 160


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
) -> str:
    try:
        import onnx
        import onnxruntime as ort
        import torch
    except ImportError as error:
        raise RuntimeError("Install nailsize-ml-tooling[training] to export the model") from error
    if not model_version.strip() or parity_atol <= 0:
        raise ValueError("Model version and a positive parity tolerance are required")

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    model.eval()
    torch.manual_seed(0)
    example = torch.rand((1, 3, INPUT_HEIGHT, INPUT_WIDTH), dtype=torch.float32)
    with torch.no_grad():
        native = model(example).detach().cpu().numpy()
    if native.shape != (1, 1, INPUT_HEIGHT, INPUT_WIDTH) or not np.isfinite(native).all():
        raise ValueError("Model output does not satisfy the inference tensor contract")

    program = torch.onnx.export(
        model,
        (example,),
        input_names=["image"],
        output_names=["mask_logits"],
        dynamo=True,
        external_data=False,
    )
    program.save(path, external_data=False)
    graph = onnx.load(path)
    del graph.metadata_props[:]
    metadata = graph.metadata_props.add()
    metadata.key = "nailsize.model_version"
    metadata.value = model_version
    onnx.checker.check_model(graph)
    onnx.save(graph, path)

    session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    exported = session.run(["mask_logits"], {"image": example.numpy()})[0]
    if exported.shape != native.shape or not np.isfinite(exported).all():
        raise RuntimeError("ONNX output does not satisfy the inference tensor contract")
    maximum_error = float(np.max(np.abs(exported - native)))
    if maximum_error > parity_atol:
        raise RuntimeError(f"ONNX parity error {maximum_error} exceeds {parity_atol}")
    return hashlib.sha256(path.read_bytes()).hexdigest()
