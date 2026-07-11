import hashlib
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from app.hand_landmarks import MediaPipeHandDetector


class FakeLandmarker:
    def __init__(self, result) -> None:
        self.result = result
        self.closed = False

    def detect(self, _image):
        return self.result

    def close(self) -> None:
        self.closed = True


def install_fake_mediapipe(monkeypatch, result) -> FakeLandmarker:
    landmarker = FakeLandmarker(result)
    hand_landmarker = SimpleNamespace(create_from_options=lambda _options: landmarker)
    vision = SimpleNamespace(
        HandLandmarkerOptions=lambda **options: options,
        HandLandmarker=hand_landmarker,
        RunningMode=SimpleNamespace(IMAGE="image"),
    )
    fake = SimpleNamespace(
        tasks=SimpleNamespace(
            BaseOptions=lambda **options: options,
            vision=vision,
        ),
        Image=lambda **options: options,
        ImageFormat=SimpleNamespace(SRGB="srgb"),
    )
    monkeypatch.setitem(sys.modules, "mediapipe", fake)
    return landmarker


def test_mediapipe_adapter_returns_one_normalized_hand(monkeypatch, tmp_path) -> None:
    raw_landmarks = [SimpleNamespace(x=0.1, y=0.2, z=-0.01) for _ in range(21)]
    result = SimpleNamespace(
        hand_landmarks=[raw_landmarks],
        handedness=[[SimpleNamespace(category_name="Left", score=0.98)]],
    )
    fake_landmarker = install_fake_mediapipe(monkeypatch, result)
    model_path = tmp_path / "hand.task"
    model_path.write_bytes(b"model")

    checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()
    with MediaPipeHandDetector(model_path, sha256=checksum) as detector:
        detection = detector.detect(np.zeros((32, 32, 3), dtype=np.uint8))

    assert detection is not None
    assert len(detection.landmarks) == 21
    assert detection.handedness_label == "Left"
    assert detection.handedness_score == pytest.approx(0.98)
    assert fake_landmarker.closed


@pytest.mark.parametrize("hand_landmarks", [[], [[SimpleNamespace(x=0, y=0, z=0)] * 20]])
def test_mediapipe_adapter_rejects_missing_or_incomplete_hand(
    monkeypatch, tmp_path, hand_landmarks
) -> None:
    result = SimpleNamespace(hand_landmarks=hand_landmarks, handedness=[])
    install_fake_mediapipe(monkeypatch, result)
    model_path = tmp_path / "hand.task"
    model_path.write_bytes(b"model")
    checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()
    detector = MediaPipeHandDetector(model_path, sha256=checksum)
    assert detector.detect(np.zeros((32, 32, 3), dtype=np.uint8)) is None
    detector.close()


def test_mediapipe_adapter_requires_model_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="model not found"):
        MediaPipeHandDetector(tmp_path / "missing.task", sha256="0" * 64)
