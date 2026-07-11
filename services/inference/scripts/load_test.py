import argparse
import asyncio
import json
import math
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class LoadSample:
    status_code: int | None
    latency_ms: float


@dataclass(frozen=True)
class LoadReport:
    requests: int
    concurrency: int
    successes: int
    errors: int
    status_counts: dict[str, int]
    throughput_rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    passed_latency_gates: bool


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("At least one latency sample is required")
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def summarize_load(
    samples: list[LoadSample], *, concurrency: int, elapsed_seconds: float
) -> LoadReport:
    if not samples or concurrency <= 0 or elapsed_seconds <= 0:
        raise ValueError("Samples, positive concurrency, and elapsed time are required")
    latencies = [sample.latency_ms for sample in samples]
    statuses = Counter(
        str(sample.status_code) if sample.status_code is not None else "transport_error"
        for sample in samples
    )
    successes = statuses.get("200", 0)
    p50 = _percentile(latencies, 0.50)
    p95 = _percentile(latencies, 0.95)
    p99 = _percentile(latencies, 0.99)
    return LoadReport(
        requests=len(samples),
        concurrency=concurrency,
        successes=successes,
        errors=len(samples) - successes,
        status_counts=dict(sorted(statuses.items())),
        throughput_rps=len(samples) / elapsed_seconds,
        p50_ms=p50,
        p95_ms=p95,
        p99_ms=p99,
        passed_latency_gates=(
            successes == len(samples) and p50 <= 2_000 and p95 <= 5_000 and p99 <= 10_000
        ),
    )


async def run_load(
    endpoint: str,
    image_bytes: bytes,
    *,
    content_type: str,
    capture_type: str,
    requests: int,
    concurrency: int,
    transport: httpx.AsyncBaseTransport | None = None,
) -> LoadReport:
    if requests <= 0 or concurrency <= 0 or concurrency > requests:
        raise ValueError("Requests and concurrency must be positive, with concurrency <= requests")
    if not image_bytes:
        raise ValueError("The load-test image cannot be empty")
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(transport=transport, timeout=15.0) as client:

        async def send_one() -> LoadSample:
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.post(
                        endpoint,
                        files={"image": ("load-test-image", image_bytes, content_type)},
                        data={"capture_type": capture_type, "reference_type": "iso_id1"},
                    )
                    status_code: int | None = response.status_code
                except httpx.HTTPError:
                    status_code = None
                return LoadSample(status_code, (time.perf_counter() - started) * 1_000)

        started = time.perf_counter()
        samples = await asyncio.gather(*(send_one() for _ in range(requests)))
        elapsed = time.perf_counter() - started
    return summarize_load(list(samples), concurrency=concurrency, elapsed_seconds=elapsed)


def _report_json(report: LoadReport, metadata: dict[str, Any]) -> str:
    return json.dumps({"metadata": metadata, "results": asdict(report)}, indent=2, sort_keys=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the NailSize API latency release gates")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--content-type", default="image/webp")
    parser.add_argument("--capture-type", default="left_fingers")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-http", action="store_true")
    arguments = parser.parse_args()

    parsed = urlparse(arguments.endpoint)
    if parsed.scheme != "https" and not (
        arguments.allow_http
        and parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost"}
    ):
        parser.error("Endpoint must use HTTPS; --allow-http is limited to localhost")
    image_bytes = arguments.image.read_bytes()
    report = asyncio.run(
        run_load(
            arguments.endpoint,
            image_bytes,
            content_type=arguments.content_type,
            capture_type=arguments.capture_type,
            requests=arguments.requests,
            concurrency=arguments.concurrency,
        )
    )
    rendered = _report_json(
        report,
        {
            "endpoint_host": parsed.hostname,
            "capture_type": arguments.capture_type,
            "content_type": arguments.content_type,
        },
    )
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if report.passed_latency_gates else 1)


if __name__ == "__main__":
    main()
