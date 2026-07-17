# NailSize Single-Nail Sizing Product Requirements

## Product summary

NailSize is a mobile-first, browser-only web application that turns one photo of one nail beside a Singapore 50-cent coin into one best-fit press-on suggestion.

The automatic beta is experimental. It is functionally implemented but has not passed representative physical sizing or supplier-tip validation.

## Goals

- Reduce the journey to one photo, one sizing action, and one result.
- Run image processing and the pinned nail model locally in the browser.
- Automatically detect the coin and nail without exposing calibration controls.
- Show the recommendation immediately after a usable detection.
- Return exactly one nearest best-fit suggestion, or request another photo when either object cannot be detected.
- Preserve the manual guided flow as rollback.

## Non-goals

- Identifying or verifying the coin denomination.
- Measuring curved nail-surface length or guaranteeing tip fit.
- Returning measurement coordinates from OpenAI or another vision-language model.
- Accounts, saved photos, analytics, server inference, or a custom nail-training dataset.
- Public accuracy claims before physical validation.

## Required flow

1. Upload one JPEG/JFIF, PNG, WebP, HEIC/HEIF, AVIF, GIF, or BMP image up to 12 MB showing one bare nail and one complete Singapore 50-cent coin on the same plane.
2. Select **Get my nail size**.
3. Normalize the image and run same-origin ONNX/WASM inference locally.
4. Detect the reference ellipse and nail width automatically.
5. Display one nearest best-fit suggestion immediately after a usable detection, including for estimates beyond the provisional chart edges.
6. If either object cannot be detected, return to upload with one plain retake message; do not ask the customer to confirm dimensions, select a finger, tap the coin, or edit markers.
7. Keep technical method, confidence, width, uncertainty, and chart versions out of the main customer result.

## Measurement contract

Method identifier: `auto-assumed23-single-v0.2.0`.

- The reference diameter is an automatic product assumption of `23.00 mm`; the app does not prove it.
- Automatic calibration uses the strongest confident round-reference proposal without customer quality review.
- A pinned YOLOv8 segmentation artifact proposes nail masks. Its score is proposal metadata, not calibrated measurement confidence.
- Deterministic geometry calculates projected transverse width from the strongest usable nail mask.
- Results use provisional chart `platform-default@1`; out-of-chart estimates map to the nearest available size 0 or 9.

## Privacy and architecture

- React 19, TypeScript, React Router, Vite, ONNX Runtime Web, and static Vercel hosting.
- Photos, contours, and measurements remain in volatile browser memory and are erased by reset/reload/close.
- Runtime network traffic is limited to same-origin GET requests for versioned static assets.
- No OpenAI key, Hugging Face runtime token, API route, database, object storage, or server image parser is required.
- Common consumer/web photo formats are detected from their bytes rather than trusted MIME metadata. HEIC/HEIF decoding is native-first with a lazy, same-origin browser fallback; the photo still never leaves the device.

## Acceptance criteria

- One valid photo and one action reach one best-fit result without choosing a digit, confirming the reference, or editing markers.
- Lower-confidence but usable nail geometry remains non-blocking and produces one result.
- The customer never sees calibration controls, confidence warnings, or an out-of-chart dead end.
- Invalid files, stale jobs, checksum failures, decode errors, and unusable geometry fail closed and can be retried.
- Reset/reload removes the session and object URLs are released.
- Lint, typecheck, unit, build, artifact audit, E2E, compatibility, and dependency checks pass.
- Staging and production serve the exact verified static artifact.

## Validation boundary

Functional completion is not physical validation. Before publishing accuracy or fit claims, compare results with technician-defined physical ground truth across representative people, devices, lighting, skin tones, nail shapes, and reference placement, then validate against the actual supplier chart.
