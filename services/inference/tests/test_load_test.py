import asyncio

import httpx
import pytest

from scripts.load_test import LoadSample, run_load, summarize_load


def test_summarizes_nearest_rank_release_gates() -> None:
    samples = [LoadSample(200, float(value)) for value in range(1, 101)]

    report = summarize_load(samples, concurrency=4, elapsed_seconds=10)

    assert report.p50_ms == 50
    assert report.p95_ms == 95
    assert report.p99_ms == 99
    assert report.throughput_rps == 10
    assert report.passed_latency_gates


def test_errors_fail_release_even_when_latency_is_fast() -> None:
    report = summarize_load(
        [LoadSample(200, 10), LoadSample(503, 10), LoadSample(None, 10)],
        concurrency=1,
        elapsed_seconds=1,
    )

    assert report.status_counts == {"200": 1, "503": 1, "transport_error": 1}
    assert report.errors == 2
    assert not report.passed_latency_gates


def test_runs_bounded_concurrent_multipart_requests() -> None:
    active = 0
    peak = 0
    bodies: list[bytes] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        bodies.append(await request.aread())
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(200, json={"status": "retake"})

    report = asyncio.run(
        run_load(
            "https://api.example/v1/measure",
            b"synthetic-image",
            content_type="image/webp",
            capture_type="right_thumb",
            requests=5,
            concurrency=2,
            transport=httpx.MockTransport(respond),
        )
    )

    assert report.successes == 5
    assert peak == 2
    assert all(b'filename="load-test-image"' in body for body in bodies)
    assert all(b'name="capture_type"' in body and b"right_thumb" in body for body in bodies)


@pytest.mark.parametrize(
    ("samples", "concurrency", "elapsed"),
    [([], 1, 1), ([LoadSample(200, 1)], 0, 1), ([LoadSample(200, 1)], 1, 0)],
)
def test_rejects_invalid_report_inputs(samples, concurrency: int, elapsed: float) -> None:
    with pytest.raises(ValueError):
        summarize_load(samples, concurrency=concurrency, elapsed_seconds=elapsed)
