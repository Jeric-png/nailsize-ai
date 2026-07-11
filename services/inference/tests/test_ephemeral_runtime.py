import asyncio
import os
import sys
from contextlib import contextmanager
from io import BytesIO
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers
from test_calibration import card_scene

from app.main import app, measure, settings
from app.pipeline import PipelineResult
from app.runtime import RuntimeModels
from app.schemas import CaptureType, NailMeasurement

client = TestClient(app, raise_server_exceptions=False)

_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
_MUTATION_EVENTS = {
    "os.chmod",
    "os.chown",
    "os.link",
    "os.mkdir",
    "os.remove",
    "os.rename",
    "os.rmdir",
    "os.symlink",
    "os.truncate",
    "os.utime",
}


class _WriteAudit:
    def __init__(self) -> None:
        self.active = False
        self.events: list[str] = []

    def __call__(self, event: str, arguments: tuple[object, ...]) -> None:
        if not self.active:
            return
        if event in _MUTATION_EVENTS:
            self.events.append(event)
            return
        if event != "open" or len(arguments) < 3:
            return
        mode = arguments[1]
        flags = arguments[2]
        if isinstance(mode, str) and any(marker in mode for marker in "wax+"):
            self.events.append("open:write-mode")
        elif isinstance(flags, int) and flags & _WRITE_FLAGS:
            self.events.append("open:write-flags")


@contextmanager
def filesystem_write_events():
    audit = _WriteAudit()
    sys.addaudithook(audit)
    audit.active = True
    try:
        yield audit.events
    finally:
        audit.active = False


def _jpeg_from_array(image: np.ndarray) -> bytes:
    encoded, payload = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert encoded
    return payload.tobytes()


def _post(payload: bytes):
    return client.post(
        "/v1/measure",
        files={"image": ("capture.jpg", payload, "image/jpeg")},
        data={"capture_type": "left_thumb", "reference_type": "iso_id1"},
    )


def test_success_path_does_not_write_photo_or_result(monkeypatch) -> None:
    measurement = NailMeasurement(
        digit="thumb",
        projected_width_mm=14.2,
        uncertainty_mm=0.3,
        recommended_size="4",
        alternate_size=None,
        confidence="high",
        contour=[(0.1, 0.2), (0.2, 0.2), (0.2, 0.4)],
    )
    monkeypatch.setattr(
        app.state,
        "runtime",
        RuntimeModels(hand_detector=object(), segmentation=object(), error_code=None),
    )
    monkeypatch.setattr(settings, "segmentation_boundary_error_px", 0.5)
    monkeypatch.setattr(
        "app.main.run_measurement_pipeline",
        lambda *_args, **_kwargs: PipelineResult(
            (measurement,), None, {"segmentation": 1, "calibrated_measurement": 1}
        ),
    )

    with filesystem_write_events() as writes:
        response = _post(_jpeg_from_array(card_scene()))

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert writes == []


def test_rejected_upload_does_not_write_photo_or_result() -> None:
    with filesystem_write_events() as writes:
        response = _post(b"not-an-image")

    assert response.status_code == 415
    assert writes == []


def test_timeout_failure_closes_upload_without_writing(monkeypatch) -> None:
    async def time_out(*_args, **_kwargs):
        raise TimeoutError("synthetic request deadline")

    request = SimpleNamespace(state=SimpleNamespace(request_id="timed-out-request"))
    upload = UploadFile(
        file=BytesIO(b"customer-photo"),
        filename="capture.jpg",
        headers=Headers({"content-type": "image/jpeg"}),
    )
    monkeypatch.setattr(upload, "read", time_out)

    with filesystem_write_events() as writes:
        with pytest.raises(TimeoutError, match="synthetic request deadline"):
            asyncio.run(
                measure(
                    request,
                    upload,
                    CaptureType.LEFT_THUMB,
                    "iso_id1",
                )
            )

    assert upload.file.closed
    assert writes == []


def test_cancelled_request_closes_upload_without_writing(monkeypatch) -> None:
    async def cancel(*_args, **_kwargs):
        raise asyncio.CancelledError

    request = SimpleNamespace(state=SimpleNamespace(request_id="cancelled-request"))
    upload = UploadFile(
        file=BytesIO(b"customer-photo"),
        filename="capture.jpg",
        headers=Headers({"content-type": "image/jpeg"}),
    )
    monkeypatch.setattr(upload, "read", cancel)

    with filesystem_write_events() as writes:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(
                measure(
                    request,
                    upload,
                    CaptureType.LEFT_THUMB,
                    "iso_id1",
                )
            )

    assert upload.file.closed
    assert writes == []
