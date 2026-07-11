import logging
from io import BytesIO

import cv2
import numpy as np
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from test_calibration import card_scene

from app.main import app, settings

client = TestClient(app, raise_server_exceptions=False)


def jpeg_fixture(with_reference: bool = False) -> bytes:
    image = Image.new("RGB", (1200, 800), "white")
    if with_reference:
        draw = ImageDraw.Draw(image)
        draw.rectangle((200, 220, 856, 634), outline="black", width=8)
    buffer = BytesIO()
    image.save(buffer, "JPEG", quality=95)
    return buffer.getvalue()


def post_image(
    payload: bytes,
    filename: str = "private-customer-name.jpg",
    headers: dict[str, str] | None = None,
):
    return client.post(
        "/v1/measure",
        files={"image": (filename, payload, "image/jpeg")},
        data={"capture_type": "left_fingers", "reference_type": "iso_id1"},
        headers=headers,
    )


def jpeg_from_array(image: np.ndarray) -> bytes:
    encoded, payload = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert encoded
    return payload.tobytes()


def test_measurement_never_returns_width_without_validated_inference() -> None:
    response = post_image(jpeg_fixture(with_reference=True))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "retake"
    assert body["measurements"] == []
    assert body["quality_issues"]


def test_no_store_header_is_present() -> None:
    response = post_image(jpeg_fixture())
    assert response.headers["cache-control"] == "no-store"


def test_cors_preflight_allows_the_configured_exact_origin() -> None:
    response = client.options(
        "/v1/measure",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,X-Request-ID",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-credentials" not in response.headers


def test_cors_preflight_rejects_an_unconfigured_origin() -> None:
    response = client.options(
        "/v1/measure",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_mime_spoofing_is_rejected() -> None:
    response = post_image(b"not an image")
    assert response.status_code == 415
    assert response.headers["cache-control"] == "no-store"


def test_encoded_limit_returns_413_without_filename_leak(monkeypatch, caplog) -> None:
    monkeypatch.setattr(settings, "max_encoded_bytes", 64)

    with caplog.at_level(logging.INFO, logger="nailsize.inference"):
        response = post_image(b"x" * 65, filename="private-client-name.jpg")

    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"
    assert "private-client-name" not in caplog.text


def test_unexpected_decoder_error_is_sanitized(monkeypatch, caplog) -> None:
    async def fail_decode(*_args, **_kwargs):
        raise RuntimeError("decoder internals must not reach the client")

    monkeypatch.setattr("app.main.decode_upload", fail_decode)

    with caplog.at_level(logging.ERROR, logger="nailsize.inference"):
        response = post_image(jpeg_fixture(), filename="private-client-name.jpg")

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"] == "INTERNAL_ERROR"
    assert "decoder internals" not in response.text
    assert "private-client-name" not in caplog.text


def test_unrecognized_extension_is_rejected() -> None:
    response = post_image(jpeg_fixture(), filename="capture.txt")
    assert response.status_code == 415


def test_valid_reference_fails_closed_at_segmentation_gate() -> None:
    response = post_image(jpeg_from_array(card_scene()))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "retake"
    assert body["measurements"] == []
    assert body["quality_issues"][0]["code"] == "LOW_CONFIDENCE"


def test_glare_returns_specific_retake_code() -> None:
    image = card_scene()
    cv2.circle(image, (1050, 110), 80, (255, 255, 255), -1)
    response = post_image(jpeg_from_array(image))
    assert response.status_code == 200
    assert response.json()["quality_issues"][0]["code"] == "GLARE"


def test_steep_angle_returns_specific_retake_code() -> None:
    corners = np.array([[180, 220], [830, 220], [660, 520], [350, 520]])
    response = post_image(jpeg_from_array(card_scene(corners)))
    assert response.status_code == 200
    assert response.json()["quality_issues"][0]["code"] == "ANGLE_TOO_STEEP"


def test_unsupported_capture_type_fails_contract() -> None:
    response = client.post(
        "/v1/measure",
        files={"image": ("x.jpg", jpeg_fixture(), "image/jpeg")},
        data={"capture_type": "unknown", "reference_type": "iso_id1"},
    )
    assert response.status_code == 422


def test_readiness_fails_closed_without_model() -> None:
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
