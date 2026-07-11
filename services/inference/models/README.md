# Runtime Models

Model binaries are fetched during a controlled build and are not stored in Git.

- Run `.venv/bin/python services/inference/scripts/fetch_hand_landmarker.py` to fetch Google's MediaPipe Hand Landmarker float16 task bundle.
- The fetch script verifies SHA-256 `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1` before installation.
- The nail-segmentation ONNX model will be added only after participant-disjoint validation and parity checks.

The runtime must fail readiness when either required model is absent or fails checksum/startup validation.
Linux images also require the `libegl1` and `libgles2` runtime libraries used by MediaPipe's native bindings.
