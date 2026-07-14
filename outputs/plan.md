# NailSize Single-Nail Release Plan

## Goal

Ship a fast browser-local beta that turns one photo of one selected nail into one best-fit suggestion using a user-confirmed `23.00 mm` round reference assumption.

## Plan

1. Route `/instant` to the single-photo experience while retaining the guided workflow as rollback.
2. Reuse pinned ONNX/WASM nail proposals and deterministic reference/width geometry.
3. Prefer automatic reference fitting; when clutter causes ambiguity, request one centre tap and fit the rim automatically.
4. Show two nail-width handles only when the proposed line needs review.
5. Return exactly one conservative suggestion or an out-of-chart result.
6. Keep photos browser-local and verify that runtime requests remain same-origin static GETs.
7. Test the supplied one-nail photo after local HEIC-to-JPEG conversion, explicitly assuming its reference is `23.00 mm`.
8. Run all release gates, deploy staging, promote the same verified artifact to production, and smoke-test the live route.

## Stop condition

The software release is complete when automated checks and deployment verification pass and the live route supports the one-photo flow. Physical accuracy remains open until a representative technician-reviewed study passes.
