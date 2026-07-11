import hashlib
from pathlib import Path

import httpx

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
MODEL_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
DESTINATION = Path(__file__).parents[1] / "models" / "hand_landmarker.task"


def main() -> None:
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    temporary = DESTINATION.with_suffix(".download")
    digest = hashlib.sha256()
    try:
        with httpx.stream("GET", MODEL_URL, follow_redirects=True, timeout=60) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_bytes():
                    digest.update(chunk)
                    output.write(chunk)
        actual = digest.hexdigest()
        if actual != MODEL_SHA256:
            raise RuntimeError(f"Hand landmarker checksum mismatch: {actual}")
        temporary.replace(DESTINATION)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Verified hand landmarker at {DESTINATION}")


if __name__ == "__main__":
    main()
