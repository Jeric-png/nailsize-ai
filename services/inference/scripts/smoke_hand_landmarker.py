import numpy as np
from fetch_hand_landmarker import DESTINATION

from app.hand_landmarks import MediaPipeHandDetector


def main() -> None:
    with MediaPipeHandDetector(DESTINATION) as detector:
        if detector.detect(np.zeros((256, 256, 3), dtype=np.uint8)) is not None:
            raise RuntimeError("Blank-image hand landmark smoke test returned a false detection")
    print("MediaPipe hand landmarker smoke test passed")


if __name__ == "__main__":
    main()
