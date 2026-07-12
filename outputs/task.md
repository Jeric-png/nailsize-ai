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
  - GitHub's manual deployment workflow now consumes isolated protected-environment variables/secrets, separate Vercel project IDs, and separate GCS state prefixes. Production additionally requires immutable successful staging deployment/smoke artifacts for the exact commit and model, copies the staging-tested container into the isolated production repository without rebuilding, and proves both repository references resolve to the same digest. A live, value-free audit now rejects missing/shadow environments, configuration-name drift, non-`main` deployment policies, missing reviewers, and production self-review. The current private-repository plan cannot supply the full required protection boundary, so no misleading unprotected environment shells were created. The checkbox remains open until a supported plan or approved external control exists and the remote environments, cross-environment repository grants, OIDC bindings, state buckets, domains, and platform projects are configured and inspected.
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
  - Exact CORS validation is active in the API. Provider-validated Terraform now defines an explicit maximum-instance cap, Cloud Armor per-IP throttle with preview/enforcement control, and fail-closed billing inputs. The checkbox remains open until staging traffic establishes the threshold, production plans are approved/applied, and live `429` plus budget notification behavior is observed.
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
  - Ten checksum-locked PNGs now cover every code the current production service can emit. The added calibrated no-hand capture passes through the real pinned MediaPipe detector to return `WRONG_NAIL_COUNT`; the added narrow mask traverses calibration, projection, uncertainty, and chart mapping to return `OUTSIDE_DEFAULT_CHART`. `UNSUPPORTED_NAIL_CONDITION` remains intentionally uncovered because the service has no honest condition-classification emitter; closing this checkbox still requires representative labeled condition data and a validated detection design.

## 5. Dataset and Model

- [x] Write the consent, capture, physical measurement, best-fit, annotation, and adjudication protocols.
- [x] Define inclusion/exclusion criteria for bare natural nails and unsupported conditions.
- [x] Create versioned annotation schemas for nail masks, digit, axis, lateral boundaries, quality, physical width, and best-fitting size.
- [x] Establish a participant-level train/validation/test split and prevent identity leakage.
- [x] Build annotation quality checks and an inter-annotator agreement report generator.
- [ ] Produce and review inter-annotator agreement reports from the collected study annotations.
  - A versioned fail-closed CLI now requires two independent technicians, at least 10% double annotation, bounded non-pickled masks, aggregate Dice/boundary/label/size/width agreement metrics, third-party adjudication of categorical differences, width differences over 0.5 mm, and reviewer-declared boundary disputes, plus named agreement and adjudication reviews. Its privacy-safe report is now mandatory in the exact model release bundle and must match the released dataset version. The checkbox remains open until real collected annotations and accountable reviews produce a passing artifact.
- [ ] Train the DeepLabV3-MobileNetV3 baseline on fingertip crops.
- [ ] Evaluate mask boundary error as well as IoU; do not approve based on IoU alone.
  - A fail-closed CLI now requires the exact locked test identities and counts, bounded binary prediction/ground-truth masks, the selected ONNX checksum/version, a validation-selected threshold review, and an accountable segmentation review. It emits aggregate IoU, Dice, mean boundary error, conservative p95 nail-boundary error, and participant-clustered intervals without identifiers or paths. The exact eleven-file release binds this report to the holdout, accuracy counts, model metadata, and released ONNX bytes. The checkbox remains open until the real selected model is evaluated on the independently locked holdout and reviewed.
- [ ] Export the selected model to ONNX and verify output parity with PyTorch.
  - A fail-closed CLI now requires the selected checkpoint's approved SHA-256 and model version, safely loads its fixed training schema, reconstructs DeepLabV3-MobileNetV3 with strict state compatibility, publishes ONNX only after CPU parity passes, and atomically records checkpoint/model identities, tensor contracts, provider, and measured error. The eleven-file release gate requires that original report and cross-checks it against the exact ONNX bytes, holdout-linked segmentation metrics, reviewed parity metadata, annotation-agreement evidence, physical best-fit calibration, approved research-dataset provenance, and the locked public holdout for the same released dataset before deployment. The checkbox remains open until a real selected checkpoint produces reviewed export evidence at or below `1e-4`.
- [ ] Benchmark ONNX Runtime on the Cloud Run CPU configuration.
  - The platform now defines a one-task, zero-retry Gen2 benchmark job using the exact digest-pinned inference image, model checksum/version, 2 vCPU, and 4 GiB. Deployment executes 20 warmups plus 200 measured CPU-provider iterations, verifies the live job/execution/log identity and fixed tensor contract, and retains only aggregate latency evidence. Production promotion requires the exact passing staging report. The p50/p95/p99 gates are necessary safeguards derived from the end-to-end targets, not substitutes for full capture latency testing. The checkbox remains open until the real released model passes a credentialed staging execution and its evidence is linked here.
- [x] Add model versioning, checksum validation, startup warmup, and readiness failure when the model cannot load.
- [ ] Publish a model card with dataset, metrics, subgroup results, limitations, and intended-use restrictions.
  - A fail-closed publisher now requires a passing locked-holdout report, immutable model/dataset identity, segmentation boundary metrics, ONNX parity, exclusions, limitations, and named model-owner, nail-tech, and privacy/security reviews. Publication remains pending real approved evidence.

## 6. Size Mapping and Results

- [x] Implement the immutable `platform-default@1` chart and unit tests for every size.
- [x] Implement next-wider-tip selection for between-size measurements.
- [x] Return an alternate size when uncertainty overlaps a boundary.
- [x] Return `OUTSIDE_DEFAULT_CHART` instead of clamping.
- [x] Keep projected millimetres primary and size numbers secondary in UI and shared text.
- [ ] Calibrate size recommendations against the physical best-fit labels.
  - A fail-closed CLI now applies the exact `platform-default@1` mapping to adjudicated physical widths from the locked holdout, requires 200 participants/2,000 nails, enforces exact/exact-or-adjacent/severe-miss gates, rejects unmappable widths, publishes participant-clustered intervals, and reports physical best-fit tip margins by reviewer-declared curvature cohort. Its privacy-safe report must match the accuracy holdout's dataset and counts in the exact release bundle. The checkbox remains open until real physical best-fit observations and accountable curvature/calibration reviews pass.
- [ ] Add repeatability tests across repeated captures of the same participant.
  - The operational-report CLI now validates exactly two complete ten-nail capture sets per participant and publishes signed, mean-absolute, and p90-absolute repeated-capture differences with clustered intervals. The checkbox remains open until the locked study data and named review are supplied.

## 7. Integration, Deployment, and Observability

- [ ] Containerize the API and bundle the verified ONNX model.
  - The non-root runtime image installs MediaPipe/native dependencies and requires both checksum-verified runtime artifacts at build time. CI builds it with a clearly non-release synthetic graph and requires checksum/version/warmup readiness. The checkbox remains open until the selected validated ONNX file is supplied and that immutable image passes the same smoke.
- [ ] Provision Artifact Registry, Cloud Run, Vercel, TLS, and environment configuration.
  - `infra/bootstrap` first defines required APIs, Artifact Registry, and a role-less runtime identity; after the validated staging image is pushed, `infra/platform` defines Cloud Run, serverless NEG, global HTTPS load balancing, managed TLS, HTTP redirect, and Cloud Armor. All roots now declare isolated GCS state. A protected, manual GitHub workflow verifies the exact published model bundle before OIDC authentication, builds only in staging, promotes the byte-identical digest into the production repository, applies all three roots with a digest-pinned image, and only then creates and verifies the exact Vercel Git-SHA deployment. The checkbox remains open until authorized staging and production applies, DNS/certificate activation, and immutable deployment evidence are complete.
- [ ] Configure Cloud Run with one worker, concurrency `1`, one warm minimum instance, 2 vCPU, 4 GiB RAM, and a 15-second timeout.
  - Both the provider-validated Terraform stack and manual recovery manifest lock the service settings, load-balancer-only ingress, and a disabled default URL. The same stack defines a separate single-task benchmark job with the identical immutable image and CPU/memory allocation. The checkbox remains open until the deployed revisions and job are inspected and benchmarked with the validated model.
- [ ] Deploy the frontend so photos post directly to the inference service rather than through a frontend server function.
  - The Vite client already calls the configured inference origin directly. After protected-environment approval, deployment automation creates the Vercel production build from the connected repository and exact Git SHA through the REST API, without the Vercel CLI, then requires that immutable deployment to become `READY` and `PROMOTED`. Deployment smoke now also fails unless a same-origin built JavaScript module contains both the exact load-balanced API origin and measurement path. Live network inspection in both configured environments remains pending.
- [ ] Add stage-level latency metrics, request/error counts, retake reasons, saturation, cold starts, and model/chart version dashboards.
  - Privacy-safe structured events now emit JSON-only Cloud Logging payloads. Validated Terraform defines the log metrics and a dashboard covering request/stage latency, outcomes, retakes, saturation, concurrency, CPU/memory, startup, billable time, and model/chart versions. Provisioning and live-data verification remain pending.
- [ ] Configure sanitized log retention for 30 days.
  - Validated Terraform configures the project `_Default` bucket for exactly 30 days. Applying and inspecting staging/production remain pending.
- [ ] Add alerts for error rate, p95 latency, instance saturation, malformed-upload spikes, and budget thresholds.
  - Validated, fail-closed Terraform defines all four incident policies and a project-scoped budget. Required thresholds, notification channels, account/currency, and amount have no defaults; authorized plan/apply and notification tests remain pending.
- [ ] Run staging smoke tests after every deployment and production smoke tests after promotion.
  - A reusable/manual GitHub workflow emits a privacy-safe, versioned JSON report covering health/readiness, immutable model identity, exact CORS allow/deny behavior, malformed-upload `415` plus `no-store`, deployed Vercel security headers, and the frontend bundle's exact direct API binding. The credentialed deployment workflow invokes it automatically after infrastructure apply, and production cannot begin cloud authentication without exact successful staging deployment, benchmark, and smoke artifacts for the same commit and model. Production then copies rather than rebuilds that container and emits a separate same-digest promotion report. The checkbox remains open until real staging and production revisions pass and artifacts are linked here.
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
  - CI forbids filesystem-write paths in the production application and persistent storage/payload beacon APIs in the browser. The API bounds declared-length and chunked multipart bodies below its configured in-memory spool rollover threshold; regression tests prove uploads above Starlette's former 1 MiB default and oversized requests never roll to disk. A runtime audit hook observes successful measurement, malformed failure, timeout, and cancellation paths with zero write/mutation events and proves interrupted uploads close. The Linux container uses a read-only root, no capabilities, no-new-privileges, and a bounded non-executable tmpfs for MediaPipe's non-customer Matplotlib cache; CI submits a malformed upload, forcibly terminates the service, and requires an empty persistent-layer diff. The checkbox remains open until the same paths and platform telemetry are observed in credentialed staging.
- [ ] Test current and previous two major browser versions required by `plan.md`.
  - Required CI now runs the complete functional/accessibility E2E flow on current Playwright Chromium with Android emulation, WebKit with iOS emulation, and desktop Chromium, Firefox, and WebKit. This is early engine-compatibility evidence only; the checkbox remains open until current and previous two branded browser majors pass on the required physical/hosted device matrix, including Edge and real Safari/Chrome builds.
- [ ] Complete automated accessibility scans and manual keyboard, VoiceOver, and TalkBack tests.
  - Axe scans cover landing, preparation, capture, accepted quality, processing, results, typed upload error, and expired-session recovery at both approved viewports. Automated keyboard focus/activation covers the primary path and excludes the programmatically triggered hidden file input from tab order. Manual keyboard and assistive-technology device passes remain pending.
- [x] Complete visual regression review against every referenced Stitch screen.

## 9. Accuracy and Performance Validation

- [ ] Complete the 100-participant/1,000-nail feasibility study.
- [ ] Confirm the four-photo approach can satisfy the measurement gates; otherwise add and validate the oblique-capture fallback before continuing.
- [ ] Lock the participant-disjoint public-release holdout before final model selection.
  - A fail-closed CLI now verifies every participant's manifest split against a protected salt file and emits only aggregate test counts plus an identifier-free commitment. Training, checkpoints, selected-model export, and the exact eleven-file release bind the approved report checksum; release also requires the segmentation and accuracy reports to reproduce the commitment and/or match the locked nail and participant counts. The checkbox remains open until a real study manifest is locked before model selection and independently reviewed.
- [ ] Evaluate at least 200 people and 2,000 held-out nails with adjudicated physical ground truth.
- [ ] Demonstrate width MAE ≤ 0.6 mm, p90 error ≤ 1.0 mm, and signed bias within ±0.2 mm.
- [ ] Demonstrate exact size ≥ 90%, exact-or-adjacent ≥ 99%, and more-than-one-size miss ≤ 1%.
- [ ] Demonstrate first-pass ten-nail completion ≥ 85% and completion after one retake ≥ 95%.
- [ ] Demonstrate invalid false acceptance ≤ 2% and valid false rejection ≤ 10%.
- [ ] Demonstrate required subgroup accuracy and rejection-rate parity.
- [ ] Load-test expected peak plus 20% and prove p50 ≤ 2s, p95 ≤ 5s, and p99 ≤ 10s per capture.
  - A bounded-concurrency staging harness now produces aggregate status/throughput/p50/p95/p99 JSON and fails the documented gates. Running it at the approved traffic target still requires a deployed validated model and staging endpoint.
- [ ] Publish reproducible accuracy, fairness, rejection, repeatability, and performance reports.
  - The accuracy-report CLI enforces the public-holdout minimums, overall measurement gates, reviewer-declared adequately sampled cohort gates, and participant-clustered confidence intervals. The operational-report CLI enforces completion and rejection gates and publishes repeatability and subgroup rejection gaps with required review references; the load harness covers performance. Real locked-study exports, completed reviews, and deployment evidence are still required.

## 10. Privacy, Release, and Goal Closure

- [x] Complete a data-flow and threat-model review.
- [ ] Verify that production photos are excluded from model-training workflows by technical controls, not policy alone.
  - CI forbids training/persistence imports and dependencies in the production service, constrains the container to the production package, and keeps model tooling manual without cloud auth or artifact ingress. Training now rejects any manifest row not carrying the exact approved-research-study origin, active-research-consent state, and locked dataset version; it requires a checksum-approved aggregate provenance report with named research/privacy reviews and carries the provenance plus manifest checksums through checkpoint, ONNX export, and the exact release bundle. Terraform creates a dedicated runtime identity with no project-role grants and bundles model assets inside the immutable image. Applied IAM inspection and deployed telemetry isolation remain pending, so this checkbox remains open.
- [ ] Publish privacy copy that accurately says images are never persistently stored and explains transient processing.
  - The product now includes a dedicated, accessibility-tested privacy notice covering browser memory, transient server buffers, sanitized operational metadata, prohibited training reuse, and safe reference-card guidance. Public publication remains pending deployment.
- [ ] Verify monitoring, backups, crash reporting, and analytics cannot capture image or result payloads.
  - A fail-closed source audit now allow-lists every production runtime dependency, Terraform resource address/type, and structured-log field; rejects persistent service types and telemetry SDKs; and requires disabled container access logs, native load-balancer metadata logging without optional fields, query-free browser uploads, query-stripping redirects, and a self-only script policy. CI retains a bounded 30-day JSON report with counts and booleans only. The checkbox remains open until applied GCP logging/IAM and Vercel project integrations are inspected and staging termination/failure telemetry is verified.
- [ ] Resolve every critical/high security issue and every severity-1/2 product defect.
  - CI runs a high-severity npm audit and Trivy filesystem scan. Every external GitHub Action is pinned to an immutable commit, a regression test rejects mutable references, and Dependabot covers npm, pip, GitHub Actions, Docker, and Terraform. On 2026-07-12, repository vulnerability alerts and automated security fixes were enabled; the live Dependabot security-alert and product-issue lists were empty. The 13 initial version-update pull requests were reviewed and closed as superseded or outside the verified compatibility bounds; React Refresh 0.5.3 and TypeScript 5.9.3 were adopted after full validation. Dependabot now suppresses unsupported major version-update noise without disabling security updates. Code scanning, secret scanning, and branch protection remain unavailable or disabled for this private repository on its current GitHub plan. This checkbox remains open until the unavailable services or approved compensating controls are inspected, deployed artifacts are scanned, and product-defect triage has accountable sign-off.
- [ ] Confirm all CI, staging, production smoke, E2E, accessibility, visual, performance, privacy, and model-validation checks are green.
- [ ] Complete the goal evidence ledger with links to every report and deployment revision.
- [ ] Obtain final product, nail-tech, privacy/security, and engineering sign-off.
- [ ] Mark the single goal complete only after every mandatory checkbox above and every release gate in `plan.md` has evidence.
