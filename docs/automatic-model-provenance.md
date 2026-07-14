# Automatic Nail Proposal Model Provenance

## Candidate artifact

- Purpose: editable nail-mask proposals used by the experimental `auto-assumed23-single-v0.1.0` product flow. The underlying artifact manifest retains its original pipeline version for compatibility; the artifact is not approved to issue unattended measurements.
- Upstream repository: [`mnemic/nails_seg_yolov8`](https://huggingface.co/mnemic/nails_seg_yolov8), revision `187ebf22c110e38d4f9f60ff2b04b29629cff11c`.
- Upstream file: `nails_seg_s_yolov8_v1.pt`.
- Upstream file SHA-256: `99b7d1c6ceb4bde32d80fe7ae8c8eb809c27d99b55cf9db54b6692afe68f4070`.
- Upstream card license: CC BY 4.0. The exported graph also embeds Ultralytics AGPL-3.0 metadata; treat AGPL-3.0 as the stricter distribution obligation pending legal review.
- Training source named by upstream: [Personal Projects / Nails Segmentation](https://universe.roboflow.com/personal-projects-jfbag/nails_segmentation), with no upstream model-card accuracy report.

## Browser export

- Exporter: Ultralytics `8.4.94`, ONNX `1.20.1`, opset 17, fixed `1×3×640×640` input, simplified graph, no embedded NMS.
- Outputs: `1×37×8400` boxes/class/mask coefficients and `1×32×160×160` mask prototypes.
- Path: `apps/web/public/models/nails_seg_s_yolov8_v1.onnx`.
- ONNX SHA-256: `6b0b806819748b0f3800982df8448e322d30b329090aedb3fa181bddbf6f17f5`.
- PyTorch-to-ONNX parity: exact aggregate mask and width metrics on the feasibility sample.

## Preliminary evidence

The candidate was evaluated on nine labelled public sample images containing 52 nail masks. At confidence `0.15`, it produced mean aggregate IoU `0.775`, minimum image IoU `0.495`, mean mask precision `0.837`, mean recall `0.893`, mean relative component-width error `7.0%`, p90 relative width error `13.5%`, and `76.9%` of component widths within `10%`.

This is optimistic feasibility evidence only: the small sample may overlap the model's training domain, contains no coin-calibrated millimetre ground truth, and is not representative of target users or devices. It supports an inspect-and-correct beta, not automatic accuracy claims.

For comparison, the generic MediaPipe Interactive Segmenter was tested on the same 52 masks with an ideal interior seed. Its best tight-crop configuration produced mean IoU `0.565` and only `13.5%` of component widths within `10%`; it was rejected as the nail-boundary proposal model.

## Runtime

- Browser engine: `onnxruntime-web@1.27.0` (MIT).
- Same-origin WASM SHA-256: `d1ab1b94b16a65b29d710d0b587b29e7bed336827577623913479b8afe8113e6`.
- Photos remain browser-local. The model and runtime are static GET-only assets; no inference provider or API key is used.

## Promotion boundary

Before default rollout, validate on participant-disjoint target photos with physical nail widths and the actual supplier chart. Every proposed mask must remain visible and editable, and quality failures must block recommendations. See `PRD.md` and `outputs/task.md` for the required accuracy, performance, privacy, accessibility, and real-device gates.
