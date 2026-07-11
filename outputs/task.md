# NailSize AI — Single Goal Task List

## Goal

Deliver, deploy, and validate the complete NailSize AI web application using Stitch project `8073142126445672722`, with calibrated nail measurement, a stateless privacy-preserving architecture, and documented evidence that every release gate in `plan.md` passes.

The goal remains open until implementation **and** validation are complete. A working mock UI, a model demo, or a deployed endpoint alone does not complete the goal.

## 0. Goal Controls and Evidence

- [x] Create a source repository and the monorepo structure defined in `plan.md`.
- [x] Add a goal evidence ledger at `docs/goal-evidence.md` linking every completed task to code, test output, deployment evidence, or validation reports.
- [x] Add `docs/decisions.md` for architecture and product deviations.
- [x] Configure CI to run formatting checks, lint, typecheck, unit tests, API contract tests, build, security scans, and E2E smoke tests.
- [ ] Configure separate development, staging, and production environments.
- [x] Record secrets only in the deployment secret manager or CI secret store; commit `.env.example` without credentials.

## 1. Stitch Design Implementation

- [x] Export or inspect the approved Stitch HTML/screens and record their screen IDs in frontend documentation.
- [x] Implement the Clinical Wireframe System tokens as CSS variables and typed theme constants.
- [x] Build shared primitives: buttons, bordered cards, labels, status messages, progress stepper, photo placeholder, measurement row, confidence badge, and error callout.
- [x] Implement the landing page from Stitch screen `0fe481c4ae524371a965bdbacd64846c`.
- [x] Implement preparation from `eedc165261574b8fa64bfbb0b109dd5c`.
- [x] Implement the reusable four-step capture flow from `a2e72e4483724093b18c67260e5350a0`.
- [x] Implement quality-check behavior from `b230e530ded64687b7d0179404a3de69`.
- [x] Implement processing behavior from `7f9fa8f92b3b43fabf43a358bfac8199`.
- [x] Implement mobile results from `7c2120dc69554f7fbcab9510ef84455c`.
- [x] Implement desktop results from `032c6ffdff5244f3a841db78c11d1861`.
- [x] Implement all typed error and recovery states represented by `440f911247a34c8989c7cf22abc057f7`.
- [x] Add responsive visual regression screenshots for 390px mobile and 1280px desktop.
- [x] Document every intentional deviation from Stitch and its accessibility or implementation reason.

## 2. Frontend Workflow

- [x] Implement the typed session state machine for preparation, four captures, retakes, processing, completion, and reset.
- [x] Implement camera capture and file upload with permission-denied fallback.
- [x] Support JPEG, PNG, WebP, HEIC, and HEIF user flows.
- [x] Normalize orientation and downscale oversized images without changing aspect ratio.
- [x] Keep selected photos and results only in memory; release object URLs and buffers on replacement, reset, navigation away, and completion.
- [x] Add placement guidance for a fully visible ISO ID-1 card and required nails.
- [x] Warn users not to photograph payment or government-ID cards.
- [x] Submit captures independently and support a targeted retake without losing accepted captures.
- [x] Overlay normalized returned contours on the local preview.
- [x] Assemble all ten measurements in browser memory.
- [x] Implement copy and native-share result summaries without including photos.
- [x] Prevent accidental duplicate requests and make technical retries idempotent from the user’s perspective.

## 3. API Foundation and Security

- [x] Scaffold FastAPI, Pydantic schemas, health/readiness endpoints, and structured error handling.
- [x] Implement the `/v1/measure` multipart contract from `plan.md`.
- [x] Generate OpenAPI and TypeScript client types in CI.
- [x] Enforce the 12 MB encoded and 25 MP decoded limits before expensive processing.
- [x] Verify extensions, MIME types, magic bytes, decoder output, and animation status.
- [x] Normalize orientation, strip EXIF, and rewrite decoded image data before inference.
- [x] Return `Cache-Control: no-store` on all measurement responses.
- [x] Close transient files and buffers in all success and failure paths.
- [ ] Add CORS origin restrictions, bot/rate controls, Cloud Run maximum instances, and billing alerts.
- [x] Add dependency, container, and static security scanning.
- [x] Add tests proving request bodies, filenames, photos, contours, widths, and results never enter logs or traces.

## 4. Calibration and Classical Computer Vision

- [x] Implement reference-card candidate detection and four-corner validation.
- [x] Reject missing, cropped, distorted, or uncertain reference cards.
- [x] Implement homography/perspective rectification using the known ID-1 dimensions.
- [x] Quantify reference corner error and propagate it into measurement uncertainty.
- [x] Implement blur, glare, clipping, angle, nail-pixel-count, and occlusion quality checks.
- [x] Implement hand landmark inference and deterministic finger crop ordering for every capture type.
- [x] Implement nail longitudinal-axis estimation and maximum valid transverse-chord measurement.
- [x] Add synthetic geometry tests with known dimensions, perspective, rotation, blur, and compression.
- [ ] Add golden-image tests for every quality rejection code.
  - Deterministic capture/mask codes are covered by checksum-locked PNGs; `WRONG_NAIL_COUNT` and `UNSUPPORTED_NAIL_CONDITION` remain pending the validated model/data path.

## 5. Dataset and Model

- [x] Write the consent, capture, physical measurement, best-fit, annotation, and adjudication protocols.
- [x] Define inclusion/exclusion criteria for bare natural nails and unsupported conditions.
- [x] Create versioned annotation schemas for nail masks, digit, axis, lateral boundaries, quality, physical width, and best-fitting size.
- [x] Establish a participant-level train/validation/test split and prevent identity leakage.
- [x] Build annotation quality checks and an inter-annotator agreement report generator.
- [ ] Produce and review inter-annotator agreement reports from the collected study annotations.
- [ ] Train the DeepLabV3-MobileNetV3 baseline on fingertip crops.
- [ ] Evaluate mask boundary error as well as IoU; do not approve based on IoU alone.
- [ ] Export the selected model to ONNX and verify output parity with PyTorch.
- [ ] Benchmark ONNX Runtime on the Cloud Run CPU configuration.
- [x] Add model versioning, checksum validation, startup warmup, and readiness failure when the model cannot load.
- [ ] Publish a model card with dataset, metrics, subgroup results, limitations, and intended-use restrictions.

## 6. Size Mapping and Results

- [x] Implement the immutable `platform-default@1` chart and unit tests for every size.
- [x] Implement next-wider-tip selection for between-size measurements.
- [x] Return an alternate size when uncertainty overlaps a boundary.
- [x] Return `OUTSIDE_DEFAULT_CHART` instead of clamping.
- [x] Keep projected millimetres primary and size numbers secondary in UI and shared text.
- [ ] Calibrate size recommendations against the physical best-fit labels.
- [ ] Add repeatability tests across repeated captures of the same participant.

## 7. Integration, Deployment, and Observability

- [ ] Containerize the API and bundle the verified ONNX model.
  - The non-root runtime image now installs MediaPipe/native dependencies and requires both checksum-verified runtime artifacts at build time. The checkbox remains open until the selected validated ONNX file is supplied and the resulting image passes readiness/smoke validation.
- [ ] Provision Artifact Registry, Cloud Run, Firebase Hosting, TLS, and environment configuration.
- [ ] Configure Cloud Run with one worker, concurrency `1`, one warm minimum instance, 2 vCPU, 4 GiB RAM, and a 15-second timeout.
- [ ] Deploy the frontend so photos post directly to the inference service rather than through a frontend server function.
- [ ] Add stage-level latency metrics, request/error counts, retake reasons, saturation, cold starts, and model/chart version dashboards.
  - Privacy-safe structured events now expose cold-start/readiness, request status/latency, decode and quality-stage latency, retake codes, and model/chart versions. Cloud Run saturation metrics and provisioned dashboards remain pending.
- [ ] Configure sanitized log retention for 30 days.
- [ ] Add alerts for error rate, p95 latency, instance saturation, malformed-upload spikes, and budget thresholds.
- [ ] Run staging smoke tests after every deployment and production smoke tests after promotion.
- [x] Document rollback for frontend, container revision, model version, and chart version.

## 8. Functional and Adversarial QA

- [x] Unit-test state transitions, chart mapping, quality rules, geometry, schemas, and sanitization.
- [ ] Contract-test all success, retake, 413, 415, 429, timeout, and 5xx responses.
  - Browser/API boundaries cover typed success and retake payloads plus 413, 415, 408/504, 429, offline, cancellation, and generic 5xx recovery. The API success branch now requires a complete calibrated semantic measurement set from the integrated pipeline. Selected validated weights and deployed edge-generated 429/timeout responses remain pending.
- [x] E2E-test the happy path for all four captures and ten results.
- [x] E2E-test every targeted retake without losing previously accepted measurements.
- [x] Test camera denial, file fallback, upload cancellation, offline interruption, retry, duplicate submission, and reset.
- [x] Test malformed images, MIME spoofing, decompression bombs, animated images, huge dimensions, corrupted HEIC, and unsupported files.
- [ ] Verify zero persistent image and measurement-result writes under success, failure, cancellation, timeout, and process termination.
  - CI forbids filesystem-write paths in the production application and persistent storage/payload beacon APIs in the browser. Deployed cancellation, timeout, process-termination, and platform-telemetry observation remain pending.
- [ ] Test current and previous two major browser versions required by `plan.md`.
- [ ] Complete automated accessibility scans and manual keyboard, VoiceOver, and TalkBack tests.
  - Axe scans cover landing, preparation, capture, accepted quality, processing, results, typed upload error, and expired-session recovery at both approved viewports. Automated keyboard focus/activation covers the primary path and excludes the programmatically triggered hidden file input from tab order. Manual keyboard and assistive-technology device passes remain pending.
- [x] Complete visual regression review against every referenced Stitch screen.

## 9. Accuracy and Performance Validation

- [ ] Complete the 100-participant/1,000-nail feasibility study.
- [ ] Confirm the four-photo approach can satisfy the measurement gates; otherwise add and validate the oblique-capture fallback before continuing.
- [ ] Lock the participant-disjoint public-release holdout before final model selection.
- [ ] Evaluate at least 200 people and 2,000 held-out nails with adjudicated physical ground truth.
- [ ] Demonstrate width MAE ≤ 0.6 mm, p90 error ≤ 1.0 mm, and signed bias within ±0.2 mm.
- [ ] Demonstrate exact size ≥ 90%, exact-or-adjacent ≥ 99%, and more-than-one-size miss ≤ 1%.
- [ ] Demonstrate first-pass ten-nail completion ≥ 85% and completion after one retake ≥ 95%.
- [ ] Demonstrate invalid false acceptance ≤ 2% and valid false rejection ≤ 10%.
- [ ] Demonstrate required subgroup accuracy and rejection-rate parity.
- [ ] Load-test expected peak plus 20% and prove p50 ≤ 2s, p95 ≤ 5s, and p99 ≤ 10s per capture.
  - A bounded-concurrency staging harness now produces aggregate status/throughput/p50/p95/p99 JSON and fails the documented gates. Running it at the approved traffic target still requires a deployed validated model and staging endpoint.
- [ ] Publish reproducible accuracy, fairness, rejection, repeatability, and performance reports.

## 10. Privacy, Release, and Goal Closure

- [x] Complete a data-flow and threat-model review.
- [ ] Verify that production photos are excluded from model-training workflows by technical controls, not policy alone.
  - CI now forbids training/persistence imports and dependencies in the production service, constrains the container to the production package, and keeps model tooling manual without cloud auth or artifact ingress. Cloud IAM and deployed telemetry isolation remain pending.
- [ ] Publish privacy copy that accurately says images are never persistently stored and explains transient processing.
- [ ] Verify monitoring, backups, crash reporting, and analytics cannot capture image or result payloads.
- [ ] Resolve every critical/high security issue and every severity-1/2 product defect.
- [ ] Confirm all CI, staging, production smoke, E2E, accessibility, visual, performance, privacy, and model-validation checks are green.
- [ ] Complete the goal evidence ledger with links to every report and deployment revision.
- [ ] Obtain final product, nail-tech, privacy/security, and engineering sign-off.
- [ ] Mark the single goal complete only after every mandatory checkbox above and every release gate in `plan.md` has evidence.
