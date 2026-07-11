from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

from .config import Settings

register_heif_opener()

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


@dataclass
class DecodedImage:
    rgb: np.ndarray
    encoded_bytes: int
    width: int
    height: int

    def close(self) -> None:
        self.rgb.fill(0)


async def decode_upload(upload: UploadFile, settings: Settings) -> DecodedImage:
    if upload.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported image format")
    extension = Path(upload.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported image extension")

    data = await upload.read(settings.max_encoded_bytes + 1)
    try:
        if len(data) > settings.max_encoded_bytes:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image exceeds 12 MB")
        try:
            with Image.open(BytesIO(data)) as source:
                if getattr(source, "is_animated", False):
                    raise HTTPException(
                        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Animated images are not supported"
                    )
                if source.format not in ALLOWED_FORMATS:
                    raise HTTPException(
                        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        "Image signature does not match an allowed format",
                    )
                width, height = source.size
                if width * height > settings.max_decoded_pixels:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        "Decoded image exceeds 25 megapixels",
                    )
                normalized = ImageOps.exif_transpose(source).convert("RGB")
                rgb = np.array(normalized, dtype=np.uint8, copy=True)
        except (UnidentifiedImageError, OSError, ValueError) as error:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Image could not be safely decoded"
            ) from error
        return DecodedImage(rgb=rgb, encoded_bytes=len(data), width=width, height=height)
    finally:
        if data:
            mutable = bytearray(data)
            mutable[:] = b"\x00" * len(mutable)
        await upload.close()


def encode_sanitized_jpeg(decoded: DecodedImage) -> bytes:
    """Rewrite pixels without source metadata for downstream inference."""
    bgr = cv2.cvtColor(decoded.rgb, cv2.COLOR_RGB2BGR)
    ok, encoded = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise ValueError("Could not normalize image")
    return encoded.tobytes()
