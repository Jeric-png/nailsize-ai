import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .hand_geometry import LANDMARK_COUNT, NormalizedLandmark

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class HandDetection:
    landmarks: tuple[NormalizedLandmark, ...]
    handedness_label: str | None
    handedness_score: float | None


class MediaPipeHandDetector:
    """Single-image MediaPipe adapter; capture_type remains the source of left/right identity."""

    def __init__(self, model_path: str | Path, *, sha256: str) -> None:
        path = Path(model_path)
        if not path.is_file():
            raise FileNotFoundError(f"Hand landmarker model not found: {path}")
        if not _SHA256_PATTERN.fullmatch(sha256):
            raise ValueError("A lowercase SHA-256 hand model checksum is required")
        if _file_sha256(path) != sha256:
            raise ValueError("Hand landmarker model checksum mismatch")
        try:
            import mediapipe as mp
        except ImportError as error:  # pragma: no cover - exercised in deployment packaging
            raise RuntimeError(
                "Install the inference 'landmarks' extra to use MediaPipe"
            ) from error

        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(path)),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.7,
        )
        self._mp = mp
        self._landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)

    def close(self) -> None:
        self._landmarker.close()

    def __enter__(self) -> "MediaPipeHandDetector":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def detect(self, rgb: NDArray[np.uint8]) -> HandDetection | None:
        if rgb.ndim != 3 or rgb.shape[2] != 3:
            raise ValueError("A three-channel RGB image is required")
        image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)
        )
        result = self._landmarker.detect(image)
        if len(result.hand_landmarks) != 1:
            return None
        raw_landmarks = result.hand_landmarks[0]
        if len(raw_landmarks) != LANDMARK_COUNT:
            return None
        handedness = result.handedness[0][0] if result.handedness and result.handedness[0] else None
        return HandDetection(
            landmarks=tuple(
                NormalizedLandmark(x=item.x, y=item.y, z=item.z) for item in raw_landmarks
            ),
            handedness_label=getattr(handedness, "category_name", None),
            handedness_score=getattr(handedness, "score", None),
        )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
