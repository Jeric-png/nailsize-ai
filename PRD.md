# NailSize Single-Nail Sizing Product Requirements

## Product summary

NailSize is a mobile-first, browser-only web application that turns one photo of one nail into one projected-width estimate and one conservative best-fit press-on suggestion. The user selects the digit and explicitly instructs the app to treat the round reference in the photo as exactly `23.00 mm`.

The automatic beta is experimental. It is functionally implemented but has not passed representative physical sizing or supplier-tip validation.

## Goals

- Reduce the journey to one digit selection, one photo, one reference confirmation, and one result.
- Run image processing and the pinned nail model locally in the browser.
- Automatically propose the reference rim and nail width; request only a one-tap reference correction when the scale cannot be established.
- Show the recommendation immediately after a usable detection and keep two-handle nail-width adjustment optional.
- Return exactly one best-fit suggestion, or fail closed when the evidence is unusable.
- Preserve the manual guided flow as rollback.

## Non-goals

- Identifying or verifying the coin denomination.
- Measuring curved nail-surface length or guaranteeing tip fit.
- Returning measurement coordinates from OpenAI or another vision-language model.
- Accounts, saved photos, analytics, server inference, or a custom nail-training dataset.
- Public accuracy claims before physical validation.

## Required flow

1. Choose thumb, index, middle, ring, or little finger.
2. Upload one JPEG/JFIF, PNG, WebP, HEIC/HEIF, AVIF, GIF, or BMP image up to 12 MB showing one bare nail and one complete round reference on the same plane.
3. Confirm: “Assume my round reference is exactly 23.00 mm.”
4. Normalize the image and run same-origin ONNX/WASM inference locally.
5. Propose the reference ellipse and nail width automatically.
6. When reference detection is ambiguous, ask for one centre tap and fit the rim automatically; do not ask for eight rim markers.
7. Display one conservative best-fit suggestion or an out-of-chart result immediately after a usable detection.
8. If confidence is lower, show a plain-language caution and offer two editable width markers as an optional correction. Never require this correction to reveal the result.
9. Keep technical method and chart versions in the product documentation rather than the main customer result.

## Measurement contract

Method identifier: `auto-assumed23-single-v0.1.0`.

- The reference diameter is a user-supplied assumption of `23.00 mm`; the app does not prove it.
- Automatic calibration fits the complete visible reference rim and rejects weak, cropped, or severely tilted geometry.
- A pinned YOLOv8 segmentation artifact proposes nail masks. Its score is proposal metadata, not calibrated measurement confidence.
- Deterministic geometry calculates projected transverse width. User-adjusted sidewalls replace the proposed width geometry.
- Uncertainty includes reference fit and boundary uncertainty. A chart-boundary result remains one conservative suggestion with a borderline warning.
- Results use provisional chart `platform-default@1` and record whether geometry was automatic or user-corrected.

## Privacy and architecture

- React 19, TypeScript, React Router, Vite, ONNX Runtime Web, and static Vercel hosting.
- Photos, contours, and measurements remain in volatile browser memory and are erased by reset/reload/close.
- Runtime network traffic is limited to same-origin GET requests for versioned static assets.
- No OpenAI key, Hugging Face runtime token, API route, database, object storage, or server image parser is required.
- Common consumer/web photo formats are detected from their bytes rather than trusted MIME metadata. HEIC/HEIF decoding is native-first with a lazy, same-origin browser fallback; the photo still never leaves the device.

## Acceptance criteria

- One valid photo reaches one best-fit result without a second confirmation step.
- Ambiguous reference detection requires at most one centre tap, not rim-by-rim marking.
- Lower-confidence but usable nail geometry is shown with a caution and is optionally correctable through two width markers.
- Invalid files, stale jobs, checksum failures, decode errors, and unusable geometry fail closed and can be retried.
- Reset/reload removes the session and object URLs are released.
- Lint, typecheck, unit, build, artifact audit, E2E, compatibility, and dependency checks pass.
- Staging and production serve the exact verified static artifact.

## Validation boundary

Functional completion is not physical validation. Before publishing accuracy or fit claims, compare results with technician-defined physical ground truth across representative people, devices, lighting, skin tones, nail shapes, and reference placement, then validate against the actual supplier chart.
