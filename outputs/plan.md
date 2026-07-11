# NailSize AI — Implementation and Validation Plan

## 1. Objective

Build and validate a production-ready, mobile-first web application that guides a customer through photographing all ten natural nails, measures each nail using calibrated computer vision, and returns millimetre measurements plus a default press-on size recommendation.

This is one end-to-end delivery goal: the work is not complete when the interface is built. Completion requires the Stitch design to be implemented, the inference pipeline to work, privacy controls to be verified, and the sizing accuracy gates to pass on a participant-disjoint validation dataset.

## 2. Credential and AI Decision

An OpenAI API key is **not required** for the sizing system.

The product uses:

- Google Stitch only as the UI and interaction design source.
- MediaPipe Hand Landmarker for locating hands, fingers, and fingertip crops.
- A purpose-trained PyTorch/Torchvision nail-segmentation model.
- ONNX Runtime for fast production inference.
- OpenCV for reference-card detection, perspective correction, contour processing, and pixel-to-millimetre conversion.
- A versioned deterministic size chart for converting millimetres to press-on sizes.

The application must not send customer photos to a general-purpose vision-language model. Accurate physical measurement depends on segmentation, calibration, geometry, and product-specific validation data—not an LLM response.

Credentials required later:

- Vercel credentials for frontend preview and production deployments.
- Google Cloud credentials for Artifact Registry, Cloud Run, monitoring, and deployment.
- The existing Stitch connection for reading the approved screens.
- CI/CD deployment credentials after a source repository is configured.

Production uploads must never be used for training unless the customer enters a separate, explicit research-consent flow. The model-development dataset is collected and stored separately.

## 3. Stitch Design Source of Truth

Use Stitch project **NailSize AI Guide**, project ID `8073142126445672722`.

### Screen mapping

| Product route/state | Stitch screen                               | Screen ID                          |
| ------------------- | ------------------------------------------- | ---------------------------------- |
| Landing             | Landing Page - Mobile Wireframe             | `0fe481c4ae524371a965bdbacd64846c` |
| Preparation         | Preparation Instructions - Mobile Wireframe | `eedc165261574b8fa64bfbb0b109dd5c` |
| Guided capture      | Guided Capture - Left Fingers               | `a2e72e4483724093b18c67260e5350a0` |
| Quality check       | Photo Quality Check                         | `b230e530ded64687b7d0179404a3de69` |
| Processing          | AI Processing Screen                        | `7f9fa8f92b3b43fabf43a358bfac8199` |
| Results, mobile     | Sizing Results - Mobile Wireframe           | `7c2120dc69554f7fbcab9510ef84455c` |
| Results, desktop    | Sizing Results - Desktop Wireframe          | `032c6ffdff5244f3a841db78c11d1861` |
| Failure states      | Supporting Error States                     | `440f911247a34c8989c7cf22abc057f7` |

The left-fingers capture screen is the reusable template for `left_fingers`, `left_thumb`, `right_fingers`, and `right_thumb`. Change instructional content and placement guides through typed configuration rather than duplicating page implementations.

### Design tokens

- Style: clinical, objective, structural, low-to-medium fidelity.
- Font: Inter for headings, labels, and body text; optional Courier Prime for technical metadata.
- Primary: `#1A202C`; page background: `#F7FAFC`; white surface: `#FFFFFF`.
- Border: `#CBD5E0`; text: `#181C1E`; secondary text: `#45474C`.
- Error: `#BA1A1A`; success must use text/icon support and never color alone.
- Spacing: 8px base grid; 16px mobile margins; 24px desktop gutters.
- Mobile: four-column fluid layout. Desktop: twelve-column layout capped at 1280px.
- Shapes: square corners, no decorative shadows, 1px borders for standard containers, 2px borders for focus, modal, and priority states.
- Primary actions: solid charcoal. Secondary actions: outlined.
- Accessibility: minimum 4.5:1 text contrast, visible focus states, semantic status announcements, and full keyboard operation.

The Stitch screens are the visual baseline. If implementation constraints require a visual deviation, document it before changing the design. Functional error states and accessibility requirements take precedence over pixel matching.

## 4. Product Workflow

1. Customer opens the landing screen and starts sizing.
2. Preparation explains bare-nail, lighting, hand-position, privacy, and reference-card requirements.
3. Customer completes four guided captures: left fingers, left thumb, right fingers, and right thumb.
4. Each image is uploaded and evaluated independently. Invalid captures return a specific retake instruction without producing a size.
5. Accepted results remain in browser memory while the remaining captures are completed.
6. The final screen displays all ten fingers, projected width in millimetres, recommended size, uncertainty/confidence, and an adjacent option when a chart boundary is crossed.
7. Customer copies or shares a text-only result summary. Photos are not included and are discarded when the session ends.

V1 is public and stateless. It has no account, saved history, artist portal, ecommerce, medical diagnosis, or persistent measurement session.

## 5. System Architecture

### Frontend

- React, TypeScript, and Vite.
- React Router with routes or route-equivalent state for landing, preparation, capture, processing, results, and terminal errors.
- A typed client-side session state machine owns the four captures and their results.
- Camera and file-upload support with permission-denied fallback.
- Client-side orientation handling, preview, safe downscaling, and object-URL cleanup.
- TanStack Query or a small typed API client for request lifecycle and retries; do not add global state infrastructure unless the session state becomes difficult to maintain with a reducer.
- Vitest, Testing Library, axe-core, and Playwright.
- Static deployment to Vercel with SPA rewrites and environment-specific inference origins.

### Inference service

- Python 3.12, FastAPI, Pydantic, and Uvicorn.
- Pillow/pillow-heif for safe decode and HEIC support.
- MediaPipe for hand landmarks and per-finger crop generation.
- OpenCV for reference geometry and measurement.
- ONNX Runtime CPU execution with the model loaded once at container startup.
- Pytest for unit and contract tests.
- Container deployed to Cloud Run with 2 vCPU, 4 GiB RAM, one Uvicorn worker, concurrency `1`, minimum instances `1`, and a 15-second application timeout.

### Model development

- Train a compact binary nail segmentation model on individual fingertip crops using PyTorch/Torchvision.
- Start with DeepLabV3-MobileNetV3. Export the accepted checkpoint to ONNX.
- Label nail masks, finger identity, base-to-tip direction, visible lateral boundaries, physical measurements, best-fitting platform tip, capture quality, and exclusion reasons.
- Split train, validation, and test data by participant, never by image.
- Maintain model cards containing dataset version, intended use, exclusions, subgroup results, thresholds, and known limitations.

### Persistence and observability

- No application database, object storage, queue, or image cache in the production measurement path.
- Images exist only in transient browser/request buffers and are released on success, retake, error, cancellation, and timeout.
- Return `Cache-Control: no-store`.
- Logs may contain request ID, encoded byte count, decoded dimensions, stage timings, model/chart version, confidence bucket, HTTP status, and machine-readable error code.
- Logs must not contain images, filenames, EXIF, contours, embeddings, nail widths, recommended sizes, or result summaries.
- Retain sanitized operational logs for 30 days.

## 6. API Contract

`POST /v1/measure` accepts one multipart capture:

- `image`: JPEG, PNG, WebP, HEIC, or HEIF; maximum 12 MB and 25 decoded megapixels.
- `capture_type`: `left_fingers | left_thumb | right_fingers | right_thumb`.
- `reference_type`: `iso_id1`.

Successful domain response:

```json
{
  "status": "ok",
  "request_id": "uuid",
  "capture_type": "left_fingers",
  "measurements": [
    {
      "digit": "index",
      "projected_width_mm": 14.2,
      "uncertainty_mm": 0.4,
      "recommended_size": "3",
      "alternate_size": "4",
      "confidence": "high",
      "contour": [
        [0.42, 0.31],
        [0.44, 0.32]
      ]
    }
  ],
  "quality_issues": [],
  "model_version": "nail-segmentation-1.0.0",
  "chart_id": "platform-default",
  "chart_version": "1",
  "processing_ms": 1830
}
```

Retake responses use HTTP 200 with `status: "retake"` and one or more typed issues such as `REFERENCE_MISSING`, `REFERENCE_INVALID`, `BLUR`, `GLARE`, `ANGLE_TOO_STEEP`, `NAIL_CROPPED`, `NAIL_OCCLUDED`, `WRONG_NAIL_COUNT`, `UNSUPPORTED_NAIL_CONDITION`, or `LOW_CONFIDENCE`.

Use HTTP 413, 415, 429, and 5xx only for payload, media, rate-limit, and infrastructure failures.

## 7. Measurement and Size Rules

- Require a fully visible, rigid ISO ID-1 reference card in the same plane as the hand. The UI must prohibit payment or government-ID cards and recommend a blank calibration or non-sensitive standard-size card.
- Detect all reference corners and reject uncertain calibration.
- Rectify perspective using the reference plane.
- Identify each finger from explicit `capture_type` and landmark order; never infer left/right without the submitted capture type.
- Derive the nail longitudinal axis, then measure the widest valid transverse chord within the nail-bed mask.
- Return the projected width transparently. Do not call it curved surface width.
- Calibrate the size recommendation against real best-fitting tips so that curvature-related bias is measured rather than assumed away.
- Default chart `platform-default@1`: size `0 = 18 mm` through size `9 = 9 mm` in 1 mm steps.
- For between-size measurements, select the next physically wider tip. If the uncertainty interval crosses a size boundary, also return the adjacent size.
- Widths outside the supported chart return `OUTSIDE_DEFAULT_CHART`; never clamp silently.

## 8. Validation and Release Gates

### Feasibility gate

Before claiming sizing accuracy, test at least 100 participants and 1,000 nails captured through the real four-photo flow. Compare projected measurements with physical measurements and best-fitting tips. If this study cannot meet the error target, stop public launch and add an oblique/curvature capture before continuing.

### Public release dataset

- Participant-disjoint holdout of at least 200 people and 2,000 nails.
- Ground truth includes digital measurement and physical best fit using the exact default tip chart.
- Two trained nail technicians independently label fit; disagreements are adjudicated.
- Report participant-clustered confidence intervals and subgroup metrics.

### Required gates

- Width MAE ≤ 0.6 mm.
- p90 absolute error ≤ 1.0 mm.
- Mean signed bias within ±0.2 mm.
- Exact chart-size agreement ≥ 90%.
- Exact-or-adjacent agreement ≥ 99%.
- More-than-one-size miss ≤ 1%.
- Complete ten-nail result on first capture set ≥ 85%; after one targeted retake ≥ 95%.
- Invalid-capture false acceptance ≤ 2%; valid-capture false rejection ≤ 10%.
- Per-capture latency p50 ≤ 2 seconds, p95 ≤ 5 seconds, p99 ≤ 10 seconds at expected peak plus 20%.
- Each adequately sampled skin-tone, curvature, width, and device cohort has MAE ≤ 0.85 mm and exact-size accuracy no more than five percentage points below overall.
- No raw image or measurement-result leakage into persistence, logging, analytics, APM, crash reporting, or caches.
- WCAG 2.2 AA with no critical/serious automated issues and no blocking VoiceOver, TalkBack, or keyboard issue.
- End-to-end coverage on current and previous two major versions of iOS Safari, Android Chrome, and desktop Chrome, Edge, Firefox, and Safari.

## 9. Delivery Structure

Use a monorepo with:

```text
apps/web/                  React/Vite application
services/inference/        FastAPI inference API
ml/                        training, evaluation, export, and model-card tooling
packages/contracts/        generated/shared API schema and enums
tests/e2e/                 cross-service Playwright tests
infra/                     Vercel, Cloud Run, monitoring, and deployment config
docs/                      privacy, model card, data protocol, and validation reports
```

The OpenAPI schema generated by FastAPI is the API source of truth. Generate TypeScript client types from it in CI and fail CI when generated contracts drift.

## 10. Definition of Done

The single goal is complete only when every checkbox in `task.md` is complete, all release gates above have fresh evidence, the deployed UI matches the approved Stitch screen structure on mobile and desktop, the public endpoint is protected and observable, and there are zero known critical defects or privacy leaks.
