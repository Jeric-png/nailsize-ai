# Runtime Models

Model binaries are fetched during a controlled build and are not stored in Git.

- Run `.venv/bin/python services/inference/scripts/fetch_hand_landmarker.py` to fetch Google's MediaPipe Hand Landmarker float16 task bundle.
- The fetch script verifies SHA-256 `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1` before installation.
- The nail-segmentation ONNX model will be added only after participant-disjoint validation and parity checks.
- Configure `MODEL_PATH`, `MODEL_SHA256`, and `MODEL_VERSION` together. Readiness remains false if the file, checksum, graph contract, version metadata, or warmup inference is invalid.
- The production Docker build requires both files in this directory, installs the pinned MediaPipe extra and native EGL/GLES libraries, and copies only the two runtime artifacts. Build the immutable image only after the selected ONNX checksum, version metadata, parity, and release metrics are approved.

The runtime must fail readiness when either required model is absent or fails checksum/startup validation.
Linux images also require the `libegl1`, `libgl1`, and `libgles2` runtime libraries used by MediaPipe's native bindings and OpenCV import path.
