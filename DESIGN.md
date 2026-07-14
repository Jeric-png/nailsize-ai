# Design

## Source of truth

- Status: experimental single-nail automatic beta prepared for release; software-tested, not physically validated.
- Last refreshed: 2026-07-14.
- Primary route: `/instant`. The guided `guided-sg50-coin-v1` route remains a rollback.
- Measurement method: `auto-assumed23-single-v0.1.0`.

## Product intent

The customer uploads one photo containing one bare nail and one round reference, chooses the digit, confirms that the reference should be treated as exactly `23.00 mm`, reviews any requested geometry, and receives one best-fit suggestion. Photos and inference stay in browser memory.

This beta optimizes for a short upload-to-result journey. It does not identify coin denomination, prove the reference is 23 mm, measure curved nail-surface length, guarantee tip fit, or establish physical accuracy.

## Experience contract

1. Choose the nail and upload one JPEG, PNG, or WebP photo.
2. Confirm the explicit `23.00 mm` reference assumption.
3. Run the pinned nail model and deterministic coin/width geometry locally.
4. If automatic reference selection is ambiguous, ask for one tap at its centre and fit the rim automatically. Never require eight rim markers in this route.
5. If the proposed nail width needs review, show two editable sidewall handles.
6. Show exactly one best-fit suggestion or an out-of-chart result, with projected width, uncertainty, chart version, and limitations.

The user may replace the photo or restart at any time. Failures must not silently become recommendations.

## Visual and content principles

- Calm, precise, mobile-first, and non-medical.
- Square white cards on `#F7FAFC`, charcoal actions, structural borders, restrained motion.
- Maintain 44 px touch targets, visible focus, keyboard-operable corrections, and live progress/error announcements.
- Use “projected width”, “best-fit suggestion”, “assumed 23.00 mm reference”, and “needs review”.
- Do not use “exact”, “validated”, “AI knows your size”, or “guaranteed fit”.
- Show one recommendation, not a list of competing sizes.

## Technical constraints

- React, TypeScript, Vite, plain CSS, and static Vercel hosting.
- ONNX Runtime Web and pinned same-origin model/WASM assets; no OpenAI API, server inference, database, account, runtime secret, or image upload.
- Automatic reference detection may be followed by a single centre tap. Nail correction uses only two width handles.
- HEIC is not a supported product upload format. The supplied HEIC was converted locally to JPEG for functional testing and was never committed.
- The pinned model has public attribution and exact hashes. The upstream card/embedded-license interpretation remains an open distribution review item.

## Validation boundaries

- The supplied one-nail photo completed the flow when its visible coin was deliberately treated as a `23.00 mm` reference. That proves functional execution only.
- Representative physical-width and supplier-tip studies are required before accuracy or fit claims.
- The provisional `platform-default@1` chart requires nail-artist approval or replacement.
- Real-device performance, accessibility, and model generalization remain separate validation gates.
