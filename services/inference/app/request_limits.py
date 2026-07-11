from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException, status
from starlette.formparsers import MultiPartParser

MULTIPART_ENVELOPE_BYTES = 64 * 1024

ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]
ASGISend = Callable[[dict[str, Any]], Awaitable[None]]
ASGIApp = Callable[[dict[str, Any], ASGIReceive, ASGISend], Awaitable[None]]


def configure_in_memory_multipart(max_encoded_bytes: int) -> int:
    """Keep an accepted multipart request below Starlette's disk rollover threshold."""
    if max_encoded_bytes <= 0:
        raise ValueError("The encoded upload limit must be positive")
    max_body_bytes = max_encoded_bytes + MULTIPART_ENVELOPE_BYTES
    MultiPartParser.spool_max_size = max_body_bytes + 1
    return max_body_bytes


class InMemoryRequestLimitMiddleware:
    """Reject oversized measurement bodies before the multipart spool can roll to disk."""

    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        if not _is_measurement_request(scope):
            await self.app(scope, receive, send)
            return

        declared_length = _content_length(scope)
        received_bytes = 0

        async def limited_receive() -> dict[str, Any]:
            nonlocal received_bytes
            if declared_length is not None and declared_length > self.max_body_bytes:
                raise HTTPException(
                    status.HTTP_413_CONTENT_TOO_LARGE,
                    "Multipart request exceeds the in-memory limit",
                )
            message = await receive()
            if message.get("type") == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_body_bytes:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        "Multipart request exceeds the in-memory limit",
                    )
            return message

        await self.app(scope, limited_receive, send)


def _is_measurement_request(scope: dict[str, Any]) -> bool:
    return (
        scope.get("type") == "http"
        and scope.get("method") == "POST"
        and scope.get("path") == "/v1/measure"
    )


def _content_length(scope: dict[str, Any]) -> int | None:
    for name, value in scope.get("headers", ()):
        if name.lower() != b"content-length":
            continue
        try:
            length = int(value)
        except ValueError as error:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Content-Length") from error
        if length < 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Content-Length")
        return length
    return None
