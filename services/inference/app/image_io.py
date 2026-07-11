from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import numpy as np
from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

from .config import Settings

register_heif_opener()

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
FORMAT_MIME_TYPES = {
    "JPEG": {"image/jpeg"},
    "PNG": {"image/png"},
    "WEBP": {"image/webp"},
    "HEIF": {"image/heic", "image/heif"},
}
FORMAT_EXTENSIONS = {
    "JPEG": {".jpg", ".jpeg"},
    "PNG": {".png"},
    "WEBP": {".webp"},
    "HEIF": {".heic", ".heif"},
}


@dataclass
class DecodedImage:
    rgb: np.ndarray
    encoded_bytes: int
    width: int
    height: int

    def close(self) -> None:
        self.rgb.fill(0)


async def decode_upload(upload: UploadFile, settings: Settings) -> DecodedImage:
    data = bytearray()
    try:
        if upload.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported image format")
        extension = Path(upload.filename or "").suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported image extension"
            )

        data = bytearray(await upload.read(settings.max_encoded_bytes + 1))
        if len(data) > settings.max_encoded_bytes:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Image exceeds 12 MB")
        try:
            with BytesIO(data) as encoded_buffer, Image.open(encoded_buffer) as source:
                image_format = source.format
                if image_format not in ALLOWED_FORMATS:
                    raise HTTPException(
                        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        "Image signature does not match an allowed format",
                    )
                if (
                    upload.content_type not in FORMAT_MIME_TYPES[image_format]
                    or extension not in FORMAT_EXTENSIONS[image_format]
                ):
                    raise HTTPException(
                        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        "Image signature, MIME type, and extension do not match",
                    )
                if getattr(source, "is_animated", False):
                    raise HTTPException(
                        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Animated images are not supported"
                    )
                if source.width * source.height > settings.max_decoded_pixels:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        "Decoded image exceeds 25 megapixels",
                    )
                with ImageOps.exif_transpose(source) as transposed:
                    width, height = transposed.size
                    with transposed.convert("RGB") as normalized:
                        rgb = np.array(normalized, dtype=np.uint8, copy=True)
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as error:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Image could not be safely decoded"
            ) from error
        return DecodedImage(rgb=rgb, encoded_bytes=len(data), width=width, height=height)
    finally:
        if data:
            data[:] = b"\x00" * len(data)
        await upload.close()
