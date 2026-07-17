# Architecture and Product Decisions

ADR-011 through ADR-020 describe the deployed guided release and its history. ADR-021 defines the feasibility-gated target for the next release. The current guided method remains the production rollback until the automatic method passes its software, physical, privacy, accessibility, performance, and rollout gates.

ADR-023 supersedes ADR-022 for the public beta interaction while retaining its local model and deterministic geometry work. Earlier ADRs remain as implementation history.

## ADR-023 — Prefer an automatic answer over calibration review

- Status: accepted 2026-07-17.
- Decision: `/instant` asks only for one photo and one sizing action. It assumes the detected reference is a 23 mm Singapore 50-cent coin, uses the strongest usable nail detection, maps out-of-chart estimates to the nearest size, and never exposes manual calibration or width markers.
- Reason: customers need a quick recommendation and did not understand reference confirmation, digit selection, confidence warnings, or marker adjustment language.
- Consequence: the result is deliberately best-effort and can be less accurate than the retained guided workflow. A photo with no usable coin or nail detection still requires a retake.

## ADR-022 — Ship one selected nail with an assumed 23 mm reference

- Status: accepted 2026-07-14.
- Decision: `/instant` accepts one photo of one chosen nail and one round reference that the user explicitly tells the app to treat as `23.00 mm`. Automatic reference fitting is followed by at most one centre tap. A usable nail detection shows one conservative suggestion immediately, with two width markers available as an optional correction.
- Reason: a two-hand workflow and precision rim marking remained too slow for the expected upload-to-result experience. The supplied cluttered one-nail photo also showed that full-frame reference selection needs a simple disambiguation gesture.
- Consequence: the app cannot claim to identify the coin or verify its diameter. A wrong assumption scales the result incorrectly. Physical accuracy, chart approval, representative performance, and fit validation remain open.

## ADR-011 — Use browser-local guided geometry

- Status: Accepted
- Decision: Measure from user-placed calibration-reference and nail-sidewall markers entirely in the React client.
- Reason: A calibrated geometric method can produce a projected width without inventing an unvalidated nail-recognition model or requiring a training dataset.
- Consequence: There is no image upload, inference API, model key, server runtime, or automated nail detection.

## ADR-012 — Calibrate with common full sheets

- Status: Superseded by ADR-020
- Decision: Support A4 (210 × 297 mm) and US Letter (215.9 × 279.4 mm), portrait only, using an independently marked four-point homography for every photo.
- Reason: These are accessible reference planes and avoid asking a user for a payment or identity card.
- Consequence: All four sheet corners and every measured nail edge must be visible and coplanar.

This decision is retained as historical rationale only. `guided-paper-v1` is not an active calibration method.

## ADR-013 — Require two independent observations

- Status: Accepted
- Decision: Require two separately positioned photos for each of four capture groups and block a group when any corresponding width differs by more than 0.6 mm.
- Reason: Repeat capture detects unstable photography or marker placement.
- Consequence: The threshold establishes repeatability only. It is not evidence of measurement accuracy or tip fit.

## ADR-014 — Separate displayed width from sizing width

- Status: Accepted
- Decision: Display the two-photo average, but map the wider agreeing observation to the size chart.
- Reason: A tip recommendation should not be narrower than either accepted reading.
- Consequence: When the average-based size crosses a chart boundary, the customer sees one conservative best-fit selection plus a generic borderline warning, not a competing size.

## ADR-015 — Treat the default chart as provisional

- Status: Accepted
- Decision: `platform-default@1` maps sizes 0–9 to 18–9 mm in 1 mm steps and selects the narrowest tip not narrower than the sizing width.
- Reason: The application needs deterministic demo behavior before an artist-specific physical tip set is approved.
- Consequence: The chart is not a fit certification. Production artists must verify or replace it against their actual tips.

## ADR-016 — Keep photos and results ephemeral

- Status: Accepted
- Decision: Hold previews, markers, and results only in the current in-memory React session. Revoke object URLs on replacement, restart, acceptance, reset, and unmount.
- Reason: The product does not need accounts or persistence to complete a sizing session.
- Consequence: Reloading or closing the page loses the session. Copy/share exports text only and only after user action.

## ADR-017 — Deploy only the static web client

- Status: Accepted
- Decision: Build with Vite and deploy the static output to Vercel through a protected manual workflow.
- Reason: The active application has no server-side processing and can run on free static hosting.
- Consequence: Deployment requires Vercel project credentials only; it requires no GCP, Hugging Face, OpenAI, model, database, or billing variables.

## ADR-018 — Separate software verification from accuracy claims

- Status: Accepted
- Decision: CI may establish geometry, workflow, privacy-boundary, compatibility, and deployment behavior, but not real-world nail-width accuracy or press-on fit.
- Reason: Camera distortion, coin placement and tolerance, human marking, nail curvature, and physical tip geometry are empirical factors.
- Consequence: Public copy must say “projected width,” retain the curvature disclaimer, and avoid validated-accuracy or guaranteed-fit claims until physical evidence exists.

## ADR-019 — Retain ML/GCP code as inactive legacy work

- Status: Accepted
- Decision: `services/inference/`, `ml/`, `infra/`, and generated API contracts may remain for historical research, but they are excluded from the active client build, CI release path, and Vercel deployment.
- Reason: Deleting research work is unnecessary, while mixing it into the current release would recreate unvalidated dependencies and cost.
- Consequence: New active-product work must not import those modules or restore `VITE_INFERENCE_API_URL`.

## ADR-020 — Use the Third Series Singapore 50-cent coin as the local scale

- Status: Accepted; supersedes ADR-012
- Decision: `guided-sg50-coin-v1` supports only the current Third Series Singapore 50-cent coin at its nominal `23.00 mm` diameter. The user must confirm the Port of Singapore and large `50`/`CENTS` design, then mark eight rim points clockwise in every prepared image.
- Reason: A small, familiar physical reference can remain beside each nail and avoids requiring the full sheet in every frame. The legal specification provides a defined `23.00 ± 0.10 mm` diameter, while mandatory design confirmation prevents silent use of older 50-cent coins with different dimensions.
- Consequence: Calibration rejects a coin under `120 px` in prepared-image/source-coordinate space, diameter spread over `8%`, opposite-centre spread over `6%`, or nails farther than `4.5` coin diameters away. A separate `120 CSS/screen px` annotation-view minimum protects marker ergonomics without serving as accuracy evidence. Readings outside `5–25 mm` also fail closed.
- Limitation: This is a nearby pixel scale with obvious-tilt rejection, not a full homography or arbitrary perspective correction. It does not establish real-world accuracy, curved-surface width, or press-on fit.
- Sources: [Singapore Currency Act legal specification](https://sso.agc.gov.sg/SL/CA1967-S347-2013?ProvIds=Sc-&ValidDate=20130611); [MAS Third Series coin release](https://www.nas.gov.sg/archivesonline/data/pdfdoc/20130228006/press_release.pdf).

## ADR-021 — Target two-photo automatic proposals with exception-only correction

- Status: Accepted for feasibility and implementation; not approved for default production rollout.
- Decision: The next method uses one complete left-hand photo and one complete right-hand photo. Browser-local pretrained vision proposes the coin ellipse and five nail boundaries per hand. Deterministic geometry produces projected widths, the user reviews the overlays, and only uncertain coins or nails require adjustment or a targeted retake.
- Reason: The eight-photo workflow requires dozens of precision placements and takes about eight minutes, which does not match the expected upload-to-recommendation product. Two photos remove structural repetition while preserving an inspectable calibration reference.
- Architecture: the lazy automatic route fetches exact-hash same-origin model/WASM assets. Deterministic image processing proposes the coin ellipse, a pinned nail-specific YOLOv8-seg model proposes nail masks, and versioned geometry/quality rules fail closed. ONNX runs sequentially in the browser; worker migration is a measured optimization, not an implemented claim. OpenAI/VLM output is not a measurement source.
- Consequence: `guided-sg50-coin-v1` remains rollback through at least one stable automatic release cycle. The automatic method cannot claim validated accuracy until representative physical comparison passes. If model licensing, proposal quality, or cold-cache performance fails its gate, retain the guided method rather than fabricate sizes.
