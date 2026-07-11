import argparse
import json
from pathlib import Path

from app.segmentation import NailSegmentationModel


def verify_runtime_model(model_path: Path, *, sha256: str, model_version: str) -> dict[str, str]:
    model = NailSegmentationModel(model_path, sha256=sha256, model_version=model_version)
    return {
        "schema_version": "nailsize-runtime-model-verification@1",
        "model_version": model.model_version,
        "model_sha256": sha256,
        "runtime_provider": "CPUExecutionProvider",
        "status": "ready",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a release model in the production runtime")
    parser.add_argument("model_path", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    report = verify_runtime_model(
        arguments.model_path,
        sha256=arguments.sha256,
        model_version=arguments.model_version,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
