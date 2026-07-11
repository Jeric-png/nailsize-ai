from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def jpeg_fixture(with_reference: bool = False) -> bytes:
    image = Image.new("RGB", (1200, 800), "white")
    if with_reference:
        draw = ImageDraw.Draw(image)
        draw.rectangle((200, 220, 856, 634), outline="black", width=8)
    buffer = BytesIO()
    image.save(buffer, "JPEG", quality=95)
    return buffer.getvalue()


def post_image(payload: bytes, filename: str = "private-customer-name.jpg"):
    return client.post(
        "/v1/measure",
        files={"image": (filename, payload, "image/jpeg")},
        data={"capture_type": "left_fingers", "reference_type": "iso_id1"},
    )


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


def test_mime_spoofing_is_rejected() -> None:
    response = post_image(b"not an image")
    assert response.status_code == 415
    assert response.headers["cache-control"] == "no-store"


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
