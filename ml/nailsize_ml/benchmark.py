import argparse
import hashlib
import json
import os
import platform
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .modeling import INPUT_HEIGHT, INPUT_WIDTH


@dataclass(frozen=True)
class BenchmarkReport:
    model_sha256: str
    provider: str
    iterations: int
    warmup_iterations: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    cpu_count: int | None
    machine: str
    platform: str
    python_version: str


def benchmark_onnx(
    model_path: str | Path,
    *,
    iterations: int = 100,
    warmup_iterations: int = 10,
) -> BenchmarkReport:
    try:
        import onnxruntime as ort
    except ImportError as error:
        raise RuntimeError("Install nailsize-ml-tooling[training] to benchmark ONNX") from error
    path = Path(model_path)
    if not path.is_file() or iterations <= 0 or warmup_iterations < 0:
        raise ValueError("A model and valid iteration counts are required")

    session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    expected_input_shape = [1, 3, INPUT_HEIGHT, INPUT_WIDTH]
    expected_output_shape = [1, 1, INPUT_HEIGHT, INPUT_WIDTH]
    if len(inputs) != 1 or list(inputs[0].shape) != expected_input_shape:
        raise ValueError("Model input does not satisfy the production tensor contract")
    if len(outputs) != 1 or list(outputs[0].shape) != expected_output_shape:
        raise ValueError("Model output does not satisfy the production tensor contract")

    tensor = np.zeros(expected_input_shape, dtype=np.float32)
    feed = {inputs[0].name: tensor}
    for _ in range(warmup_iterations):
        session.run([outputs[0].name], feed)

    durations_ms: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        result = session.run([outputs[0].name], feed)[0]
        durations_ms.append((time.perf_counter_ns() - started) / 1_000_000)
        if result.shape != tuple(expected_output_shape) or not np.isfinite(result).all():
            raise RuntimeError("ONNX Runtime returned an invalid output")
    durations = np.asarray(durations_ms, dtype=float)
    return BenchmarkReport(
        model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        provider=session.get_providers()[0],
        iterations=iterations,
        warmup_iterations=warmup_iterations,
        p50_ms=float(np.quantile(durations, 0.50)),
        p95_ms=float(np.quantile(durations, 0.95)),
        p99_ms=float(np.quantile(durations, 0.99)),
        mean_ms=float(durations.mean()),
        cpu_count=os.cpu_count(),
        machine=platform.machine(),
        platform=platform.platform(),
        python_version=platform.python_version(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the NailSize ONNX segmentation model")
    parser.add_argument("model", type=Path)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmup-iterations", type=int, default=10)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = benchmark_onnx(
        arguments.model,
        iterations=arguments.iterations,
        warmup_iterations=arguments.warmup_iterations,
    )
    payload = json.dumps(asdict(report), indent=2) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main()
