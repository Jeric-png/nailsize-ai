import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from numpy.typing import NDArray

INPUT_WIDTH = 160
INPUT_HEIGHT = 224
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class ModelLoadError(RuntimeError):
    pass


@dataclass(frozen=True)
class SegmentationResult:
    mask: NDArray[np.uint8]
    confidence: float


class NailSegmentationModel:
    def __init__(self, model_path: str | Path, *, sha256: str, model_version: str) -> None:
        path = Path(model_path)
        if not path.is_file():
            raise ModelLoadError(f"Segmentation model not found: {path}")
        if not _SHA256_PATTERN.fullmatch(sha256):
            raise ModelLoadError("A lowercase SHA-256 model checksum is required")
        actual = _file_sha256(path)
        if actual != sha256:
            raise ModelLoadError(f"Segmentation model checksum mismatch: {actual}")
        try:
            self._session = ort.InferenceSession(
                path,
                providers=["CPUExecutionProvider"],
            )
        except Exception as error:
            raise ModelLoadError("ONNX Runtime could not load the segmentation model") from error
        inputs = self._session.get_inputs()
        outputs = self._session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1:
            raise ModelLoadError("Segmentation model must expose one input and one output")
        if list(inputs[0].shape) != [1, 3, INPUT_HEIGHT, INPUT_WIDTH]:
            raise ModelLoadError("Unexpected segmentation input shape")
        if list(outputs[0].shape) != [1, 1, INPUT_HEIGHT, INPUT_WIDTH]:
            raise ModelLoadError("Unexpected segmentation output shape")
        metadata = self._session.get_modelmeta().custom_metadata_map
        if metadata.get("nailsize.model_version") != model_version:
            raise ModelLoadError("Segmentation model version metadata does not match configuration")
        self._input_name = inputs[0].name
        self._output_name = outputs[0].name
        self.model_version = model_version
        self._run(np.zeros((1, 3, INPUT_HEIGHT, INPUT_WIDTH), dtype=np.float32))

    def segment(self, rgb: NDArray[np.uint8]) -> SegmentationResult:
        if rgb.shape != (INPUT_HEIGHT, INPUT_WIDTH, 3) or rgb.dtype != np.uint8:
            raise ValueError(f"Expected uint8 RGB crop {INPUT_WIDTH}x{INPUT_HEIGHT}")
        normalized = rgb.astype(np.float32) / 255.0
        normalized = (normalized - _MEAN) / _STD
        tensor = np.ascontiguousarray(normalized.transpose(2, 0, 1)[None, ...])
        logits = self._run(tensor)[0, 0]
        probabilities = 1.0 / (1.0 + np.exp(-np.clip(logits, -30, 30)))
        mask = _largest_component((probabilities >= 0.5).astype(np.uint8))
        foreground = probabilities[mask > 0]
        confidence = float(foreground.mean()) if foreground.size else 0.0
        return SegmentationResult(mask=mask, confidence=confidence)

    def _run(self, tensor: NDArray[np.float32]) -> NDArray[np.float32]:
        result = self._session.run([self._output_name], {self._input_name: tensor})[0]
        output = np.asarray(result, dtype=np.float32)
        if output.shape != (1, 1, INPUT_HEIGHT, INPUT_WIDTH) or not np.isfinite(output).all():
            raise RuntimeError("Segmentation model returned an invalid tensor")
        return output


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _largest_component(mask: NDArray[np.uint8]) -> NDArray[np.uint8]:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count <= 1:
        return np.zeros_like(mask)
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (labels == largest).astype(np.uint8)
