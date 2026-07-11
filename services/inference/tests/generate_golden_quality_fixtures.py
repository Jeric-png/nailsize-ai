"""Regenerate deterministic quality-gate PNG fixtures and their checksums."""

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "golden_quality"


def card_scene(corners: np.ndarray | None = None) -> np.ndarray:
    image = np.full((900, 1200, 3), 210, dtype=np.uint8)
    for x in range(0, 1200, 24):
        cv2.line(image, (x, 0), (x, 899), (190, 190, 190), 1)
    for y in range(0, 900, 24):
        cv2.line(image, (0, y), (1199, y), (190, 190, 190), 1)
    if corners is None:
        corners = np.array([[200, 220], [856, 220], [856, 634], [200, 634]])
    cv2.fillConvexPoly(image, corners.astype(np.int32), (238, 238, 238))
    cv2.polylines(image, [corners.astype(np.int32)], True, (15, 15, 15), 8)
    return image


def fixtures() -> dict[str, tuple[np.ndarray, str, str]]:
    valid = card_scene()
    glare = valid.copy()
    cv2.circle(glare, (1050, 110), 80, (255, 255, 255), -1)

    missing = np.full((900, 1200, 3), 210, dtype=np.uint8)
    for coordinate in range(0, 1200, 24):
        cv2.line(missing, (coordinate, 0), (coordinate, 899), (80, 80, 80), 2)
    for coordinate in range(0, 900, 24):
        cv2.line(missing, (0, coordinate), (1199, coordinate), (80, 80, 80), 2)

    low_pixels = np.zeros((120, 120), dtype=np.uint8)
    cv2.circle(low_pixels, (60, 60), 5, 255, -1)
    cropped = np.zeros((120, 120), dtype=np.uint8)
    cv2.rectangle(cropped, (0, 25), (50, 95), 255, -1)
    occluded = np.zeros((120, 120), dtype=np.uint8)
    cv2.ellipse(occluded, (60, 60), (30, 45), 0, 0, 360, 255, -1)
    cv2.circle(occluded, (60, 60), 15, 0, -1)

    return {
        "blur.png": (cv2.GaussianBlur(valid, (91, 91), 25), "capture", "BLUR"),
        "glare.png": (glare, "capture", "GLARE"),
        "angle-too-steep.png": (
            card_scene(np.array([[180, 220], [830, 220], [660, 520], [350, 520]])),
            "capture",
            "ANGLE_TOO_STEEP",
        ),
        "reference-invalid.png": (
            card_scene(np.array([[250, 180], [750, 180], [750, 680], [250, 680]])),
            "capture",
            "REFERENCE_INVALID",
        ),
        "reference-missing.png": (missing, "capture", "REFERENCE_MISSING"),
        "nail-low-pixels.png": (low_pixels, "mask", "LOW_CONFIDENCE"),
        "nail-cropped.png": (cropped, "mask", "NAIL_CROPPED"),
        "nail-occluded.png": (occluded, "mask", "NAIL_OCCLUDED"),
    }


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, str]] = []
    for filename, (image, evaluator, expected_code) in fixtures().items():
        path = FIXTURE_DIR / filename
        if not cv2.imwrite(str(path), image, [cv2.IMWRITE_PNG_COMPRESSION, 9]):
            raise RuntimeError(f"Could not write {path}")
        manifest.append(
            {
                "file": filename,
                "evaluator": evaluator,
                "expected_code": expected_code,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    (FIXTURE_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
