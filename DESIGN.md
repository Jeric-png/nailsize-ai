# Design

## Source of truth

- Status: experimental single-nail automatic beta prepared for release; software-tested, not physically validated.
- Last refreshed: 2026-07-17.
- Primary route: `/instant`. The guided `guided-sg50-coin-v1` route remains a rollback.
- Measurement method: `auto-assumed23-single-v0.2.0`.

## Product intent

The customer uploads one photo containing one bare nail and one Singapore 50-cent coin, selects one sizing button, and receives one best-fit suggestion. Photos and inference stay in browser memory. Calibration and width editing are not customer tasks.

This beta optimizes for a short upload-to-result journey. It does not identify coin denomination, prove the reference is 23 mm, measure curved nail-surface length, guarantee tip fit, or establish physical accuracy.

## Experience contract

1. Upload one common photo format: JPEG/JFIF, PNG, WebP, HEIC/HEIF, AVIF, GIF, or BMP.
2. Select **Get my nail size**.
3. Run the pinned nail model and deterministic coin/width geometry locally.
4. Show exactly one nearest best-fit suggestion immediately after a usable detection.
5. If detection fails, show one short retake message and return to upload.
6. Keep finger selection, reference confirmation, millimetres, confidence, uncertainty, method details, and editable markers out of the customer journey.

The user may replace the photo or restart at any time. Failures must not silently become recommendations.

## Visual and content principles

- Calm, precise, mobile-first, and non-medical.
- Square white cards on `#F7FAFC`, charcoal actions, structural borders, restrained motion.
- Maintain 44 px touch targets, visible focus, and live progress/error announcements.
- Lead with “recommended press-on size”. Keep the fit limitation to one short sentence.
- Do not use “exact”, “validated”, “AI knows your size”, or “guaranteed fit”.
- Show one recommendation, not a list of competing sizes.

## Technical constraints

- React, TypeScript, Vite, plain CSS, and static Vercel hosting.
- ONNX Runtime Web and pinned same-origin model/WASM assets; no OpenAI API, server inference, database, account, runtime secret, or image upload.
- Automatic reference and nail detection either produce a result or request another photo; no correction UI is exposed.
- Common photo formats are normalized to metadata-free JPEG in browser memory. HEIC/HEIF uses native decoding where available and a lazy local decoder elsewhere; no selected photo is uploaded.
- The pinned model has public attribution and exact hashes. The upstream card/embedded-license interpretation remains an open distribution review item.

## Validation boundaries

- The supplied one-nail photo completed the flow when its visible coin was deliberately treated as a `23.00 mm` reference. That proves functional execution only.
- Representative physical-width and supplier-tip studies are required before accuracy or fit claims.
- The provisional `platform-default@1` chart requires nail-artist approval or replacement.
- Real-device performance, accessibility, and model generalization remain separate validation gates.
