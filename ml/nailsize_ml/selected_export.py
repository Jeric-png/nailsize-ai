import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .modeling import export_selected_checkpoint


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export one checksum-approved NailSize training checkpoint to verified ONNX"
    )
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--expected-checkpoint-sha256", required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--onnx", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--parity-atol", type=float, default=1e-4)
    arguments = parser.parse_args()
    report = export_selected_checkpoint(
        arguments.checkpoint,
        arguments.onnx,
        arguments.report,
        expected_checkpoint_sha256=arguments.expected_checkpoint_sha256,
        expected_model_version=arguments.model_version,
        parity_atol=arguments.parity_atol,
    )
    print(json.dumps(asdict(report), sort_keys=True))


if __name__ == "__main__":
    main()
