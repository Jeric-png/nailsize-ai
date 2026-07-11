import asyncio
import struct
import zlib
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image
from starlette.datastructures import Headers

from app.config import Settings
from app.image_io import decode_upload


def encoded_image(format_name: str, *, size: tuple[int, int] = (32, 24)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "purple").save(buffer, format_name)
    return buffer.getvalue()


def animated_webp() -> bytes:
    buffer = BytesIO()
    first = Image.new("RGB", (32, 24), "purple")
    second = Image.new("RGB", (32, 24), "pink")
    first.save(buffer, "WEBP", save_all=True, append_images=[second], duration=100, loop=0)
    return buffer.getvalue()


def oriented_jpeg() -> bytes:
    buffer = BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (32, 24), "purple").save(buffer, "JPEG", exif=exif)
    return buffer.getvalue()


def png_with_dimensions(width: int, height: int) -> bytes:
    def chunk(kind: bytes, content: bytes) -> bytes:
        checksum = zlib.crc32(kind + content) & 0xFFFFFFFF
        return struct.pack(">I", len(content)) + kind + content + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IEND", b"")


def make_upload(payload: bytes, *, filename: str, content_type: str) -> UploadFile:
    return UploadFile(
        BytesIO(payload),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def decode(upload: UploadFile, settings: Settings | None = None):
    return asyncio.run(decode_upload(upload, settings or Settings()))


@pytest.mark.parametrize(
    ("format_name", "filename", "content_type"),
    [
        ("JPEG", "capture.jpg", "image/jpeg"),
        ("PNG", "capture.png", "image/png"),
        ("WEBP", "capture.webp", "image/webp"),
    ],
)
def test_static_supported_images_decode_and_close_upload(
    format_name: str, filename: str, content_type: str
) -> None:
    upload = make_upload(encoded_image(format_name), filename=filename, content_type=content_type)

    decoded = decode(upload)

    assert decoded.rgb.shape == (24, 32, 3)
    assert upload.file.closed
    decoded.close()
    assert not decoded.rgb.any()


def test_exif_orientation_is_applied_before_metadata_free_inference() -> None:
    upload = make_upload(oriented_jpeg(), filename="capture.jpg", content_type="image/jpeg")

    decoded = decode(upload)

    assert (decoded.width, decoded.height) == (24, 32)
    assert decoded.rgb.shape == (32, 24, 3)
    assert upload.file.closed
    decoded.close()


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("capture.jpg", "image/png"),
        ("capture.png", "image/jpeg"),
        ("capture.jpg", "image/jpeg"),
    ],
)
def test_signature_must_match_mime_and_extension(filename: str, content_type: str) -> None:
    upload = make_upload(encoded_image("PNG"), filename=filename, content_type=content_type)

    with pytest.raises(HTTPException) as raised:
        decode(upload)

    assert raised.value.status_code == 415
    assert upload.file.closed


def test_rejects_encoded_payload_over_limit_and_closes_upload() -> None:
    upload = make_upload(b"x" * 65, filename="capture.jpg", content_type="image/jpeg")

    with pytest.raises(HTTPException) as raised:
        decode(upload, Settings(max_encoded_bytes=64))

    assert raised.value.status_code == 413
    assert upload.file.closed


def test_rejects_decoded_pixel_count_over_limit() -> None:
    upload = make_upload(
        encoded_image("PNG", size=(20, 20)),
        filename="capture.png",
        content_type="image/png",
    )

    with pytest.raises(HTTPException) as raised:
        decode(upload, Settings(max_decoded_pixels=399))

    assert raised.value.status_code == 413
    assert upload.file.closed


def test_rejects_animated_webp() -> None:
    upload = make_upload(animated_webp(), filename="capture.webp", content_type="image/webp")

    with pytest.raises(HTTPException) as raised:
        decode(upload)

    assert raised.value.status_code == 415
    assert upload.file.closed


def test_rejects_corrupted_heic() -> None:
    upload = make_upload(b"not-a-heif", filename="capture.heic", content_type="image/heic")

    with pytest.raises(HTTPException) as raised:
        decode(upload)

    assert raised.value.status_code == 415
    assert upload.file.closed


def test_rejects_decompression_bomb_header() -> None:
    upload = make_upload(
        png_with_dimensions(100_000, 100_000),
        filename="capture.png",
        content_type="image/png",
    )

    with pytest.raises(HTTPException) as raised:
        decode(upload)

    assert raised.value.status_code == 415
    assert upload.file.closed


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [("capture.jpg", "text/plain"), ("capture.txt", "image/jpeg")],
)
def test_early_metadata_rejections_still_close_upload(filename: str, content_type: str) -> None:
    upload = make_upload(encoded_image("JPEG"), filename=filename, content_type=content_type)

    with pytest.raises(HTTPException) as raised:
        decode(upload)

    assert raised.value.status_code == 415
    assert upload.file.closed
