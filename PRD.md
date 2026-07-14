# NailSize Single-Nail Sizing Product Requirements

## Product summary

NailSize is a mobile-first, browser-only web application that turns one photo of one nail into one reviewable projected-width estimate and one conservative best-fit press-on suggestion. The user selects the digit and explicitly instructs the app to treat the round reference in the photo as exactly `23.00 mm`.

The automatic beta is experimental. It is functionally implemented but has not passed representative physical sizing or supplier-tip validation.

## Goals

- Reduce the journey to one digit selection, one photo, one reference confirmation, and one result.
- Run image processing and the pinned nail model locally in the browser.
- Automatically propose the reference rim and nail width; request only a one-tap reference correction or two-handle width review when needed.
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
2. Upload one JPEG, PNG, or WebP image up to 12 MB showing one bare nail and one complete round reference on the same plane.
3. Confirm: “Assume my round reference is exactly 23.00 mm.”
4. Normalize the image and run same-origin ONNX/WASM inference locally.
5. Propose the reference ellipse and nail width automatically.
6. When reference detection is ambiguous, ask for one centre tap and fit the rim automatically; do not ask for eight rim markers.
7. When the proposed width is uncertain, show two editable sidewall handles for review.
8. Display one conservative best-fit suggestion or an out-of-chart result, plus width, uncertainty, method/chart versions, and a no-fit-guarantee notice.

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
- HEIC is not accepted; the supplied test image is converted locally to JPEG outside the product.

## Acceptance criteria

- One valid photo can reach one reviewable best-fit result.
- Ambiguous reference detection requires at most one centre tap, not rim-by-rim marking.
- Uncertain nail geometry is recoverable through two sidewall handles.
- Invalid files, stale jobs, checksum failures, decode errors, and unusable geometry fail closed and can be retried.
- Reset/reload removes the session and object URLs are released.
- Lint, typecheck, unit, build, artifact audit, E2E, compatibility, and dependency checks pass.
- Staging and production serve the exact verified static artifact.

## Validation boundary

Functional completion is not physical validation. Before publishing accuracy or fit claims, compare results with technician-defined physical ground truth across representative people, devices, lighting, skin tones, nail shapes, and reference placement, then validate against the actual supplier chart.
