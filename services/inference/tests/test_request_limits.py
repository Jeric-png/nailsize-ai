import asyncio

import pytest
from fastapi import HTTPException
from starlette.formparsers import MultiPartParser

from app.request_limits import (
    MULTIPART_ENVELOPE_BYTES,
    InMemoryRequestLimitMiddleware,
    configure_in_memory_multipart,
)


def measurement_scope(headers=()):
    return {
        "type": "http",
        "method": "POST",
        "path": "/v1/measure",
        "headers": headers,
    }


def test_configuration_places_disk_rollover_above_the_total_body_limit(monkeypatch) -> None:
    monkeypatch.setattr(MultiPartParser, "spool_max_size", MultiPartParser.spool_max_size)
    max_body_bytes = configure_in_memory_multipart(1024)

    assert max_body_bytes == 1024 + MULTIPART_ENVELOPE_BYTES
    assert MultiPartParser.spool_max_size == max_body_bytes + 1
    with pytest.raises(ValueError, match="positive"):
        configure_in_memory_multipart(0)


def test_declared_oversize_is_rejected_before_reading_the_body() -> None:
    receive_called = False

    async def receive():
        nonlocal receive_called
        receive_called = True
        return {"type": "http.request", "body": b"payload", "more_body": False}

    async def downstream(_scope, downstream_receive, _send):
        await downstream_receive()

    middleware = InMemoryRequestLimitMiddleware(downstream, max_body_bytes=10)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            middleware(
                measurement_scope(((b"content-length", b"11"),)),
                receive,
                _unused_send,
            )
        )

    assert raised.value.status_code == 413
    assert receive_called is False


def test_chunked_oversize_is_rejected_before_the_excess_chunk_reaches_the_app() -> None:
    messages = iter(
        (
            {"type": "http.request", "body": b"123456", "more_body": True},
            {"type": "http.request", "body": b"78901", "more_body": False},
        )
    )
    downstream_bodies = []

    async def receive():
        return next(messages)

    async def downstream(_scope, downstream_receive, _send):
        downstream_bodies.append((await downstream_receive())["body"])
        downstream_bodies.append((await downstream_receive())["body"])

    middleware = InMemoryRequestLimitMiddleware(downstream, max_body_bytes=10)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(middleware(measurement_scope(), receive, _unused_send))

    assert raised.value.status_code == 413
    assert downstream_bodies == [b"123456"]


def test_non_measurement_routes_pass_through_unchanged() -> None:
    called = False

    async def downstream(scope, receive, send):
        nonlocal called
        called = True
        assert scope["path"] == "/health"
        assert (await receive())["body"] == b""
        await send({"type": "http.response.start", "status": 200, "headers": []})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    sent = []

    async def send(message):
        sent.append(message)

    middleware = InMemoryRequestLimitMiddleware(downstream, max_body_bytes=10)
    asyncio.run(
        middleware(
            {"type": "http", "method": "GET", "path": "/health", "headers": ()},
            receive,
            send,
        )
    )

    assert called is True
    assert sent[0]["status"] == 200


async def _unused_send(_message):
    raise AssertionError("No response should be sent directly by the request limiter")
