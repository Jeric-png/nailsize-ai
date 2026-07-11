from dataclasses import dataclass

from .config import Settings
from .hand_landmarks import MediaPipeHandDetector
from .segmentation import NailSegmentationModel


@dataclass
class RuntimeModels:
    hand_detector: MediaPipeHandDetector | None = None
    segmentation: NailSegmentationModel | None = None
    error_code: str | None = "MODEL_UNAVAILABLE"

    @property
    def ready(self) -> bool:
        return self.hand_detector is not None and self.segmentation is not None

    def close(self) -> None:
        if self.hand_detector is not None:
            self.hand_detector.close()


def load_runtime_models(settings: Settings) -> RuntimeModels:
    if settings.model_version == "unavailable" or not settings.model_sha256:
        return RuntimeModels()
    hand_detector: MediaPipeHandDetector | None = None
    try:
        hand_detector = MediaPipeHandDetector(
            settings.hand_landmarker_path,
            sha256=settings.hand_landmarker_sha256,
        )
        segmentation = NailSegmentationModel(
            settings.model_path,
            sha256=settings.model_sha256,
            model_version=settings.model_version,
        )
        return RuntimeModels(
            hand_detector=hand_detector,
            segmentation=segmentation,
            error_code=None,
        )
    except (FileNotFoundError, ValueError, RuntimeError):
        if hand_detector is not None:
            hand_detector.close()
        return RuntimeModels(error_code="MODEL_INITIALIZATION_FAILED")
