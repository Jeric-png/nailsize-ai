# Release Readiness

The single-nail automatic beta is prepared for deployment. Readiness is split into software, distribution, performance, privacy, and physical-validation evidence. Passing one category does not imply another has passed.

## Automatic client gate

A candidate is technically ready only when the same commit satisfies all of the following:

- `npm ci`, lint, typecheck, unit tests, build, and `verify:bundle` pass;
- Chromium E2E plus Chromium/Firefox/WebKit compatibility suites pass;
- `npm audit --audit-level=high` and the filesystem Trivy scan have no blocking finding;
- the product result identifies `auto-assumed23-single-v0.1.0`, while manifest tests pin the exact model revision/hash, ONNX tensor shapes, runtime hashes, calibration, measurement, quality-profile, and chart versions;
- preprocessing, model-runtime, postprocessing, mask-quality, coin-detector, ellipse-calibration, transverse-width, uncertainty, and chart-boundary tests pass;
- component/E2E tests prove one local photo can reach one selected best-fit suggestion for the chosen nail, uncertain reference/nail evidence requires correction, rejected photos fail closed, competing boundary sizes are not shown, and copy is text only;
- the beta requires explicit confirmation that the visible round reference should be assumed to be exactly `23.00 mm` and never claims to verify its denomination;
- lifecycle tests cover object URL, decoded pixel, canvas, tensor, and session cleanup on replacement, failure, reset, reload, and unmount;
- request-observing tests see only expected same-origin `GET` navigation and static-asset requests, with no photo/result request body;
- synthetic JPEG, PNG, WebP, HEIC, AVIF, GIF, and BMP fixtures normalize successfully in current Chromium, Firefox, and WebKit without external or non-`GET` requests;
- the retained guided fallback still passes its eight-point calibration, two-observation repeatability, targeted-retake, marker accessibility, and cleanup tests; and
- current iOS Safari and Android Chrome remain required for release-quality capture/upload, local inference, review/correction, results, copy, reset, low-memory, and failure-recovery evidence.

Software tests establish implementation behavior, not real-world sizing accuracy.

## Model distribution gate

The candidate model card identifies CC BY 4.0, requires attribution, and the exported ONNX graph embeds AGPL-3.0 metadata. This public repository preserves upstream revision, source/export hashes, attribution, conversion details, and benchmark limitations in [`automatic-model-provenance.md`](automatic-model-provenance.md). The beta may be distributed with that notice, but long-term licensing interpretation remains an explicit project risk and must be reviewed before commercial reliance.

The lazy HEIC/HEIF fallback is the pinned LGPL-3.0 `heic-to` package described in [`image-decoder-provenance.md`](image-decoder-provenance.md). Preserve its source/license notice and include it in the same distribution review; normal JPEG/PNG/WebP/AVIF/GIF/BMP visits do not load that chunk.

## Performance and usability gate

The experience should complete promptly from one photo, but no public duration promise is approved. Measure model download, warm-up, inference, review time, failures, and low-memory behavior separately on named phones.

Also verify that automatic review is materially faster and easier than the guided fallback, including for users who need one correction or retake.

## Configuration and privacy gate

Confirm before promotion:

- Vercel receives only the protected project/team/deployment values documented in [`deployment.md`](deployment.md); the application itself has no runtime secret or API key;
- there are no API routes, functions, analytics, Speed Insights, replay, error-reporting SDKs, persistent stores, or injected integrations;
- CSP contains `connect-src 'self'`, same-origin scripts plus `wasm-unsafe-eval`, and local-worker restrictions; COOP/COEP/CORP headers match the committed policy;
- source maps and legacy/remote inference bindings are absent;
- the release manifest and exact ONNX/WASM hashes match the reviewed artifact; and
- production still requires `DEPLOY_PRODUCTION`, environment approval, byte-identity checks, staged runtime smoke, and post-promotion verification.

No GCP, Cloud Run, Terraform, domain/capacity/monitoring/billing, OpenAI, Hugging Face inference, model-provider, or database variable belongs to the client. The bundled model is a static release asset, not a secret or runtime provider.

## Physical sizing validation gate

Before saying “validated,” “accurate,” or “fits,” independently review and execute [`data-protocol.md`](data-protocol.md) against technician-defined physical ground truth and the actual supplier tip set. Use participant-disjoint target photos, representative hands/devices/conditions, and report millimetre error, signed bias, missingness, correction/retake rates, size agreement, curvature effects, and subgroup performance.

The current public-sample segmentation benchmark is feasibility evidence only. Model confidence, visible overlays, deterministic geometry, coin tolerance, or a green client release cannot prove physical width or fit. `platform-default@1` remains provisional; borderline and strongly curved nails require an artist or physical sizing kit.

The guided fallback's `0.6 mm` rule demonstrates repeatability only and is not an accuracy target or confidence interval.

## Evidence and stop conditions

For an approved release, record the commit, CI run, immutable deployment URL, artifact digest, model/runtime hashes, license decision, device/browser versions, performance sample, reviewers, and known limitations in `docs/goal-evidence.md`. Never record credentials, photos, contours, coordinates, or individual results.

Block or roll back for failed software/security checks, unexpected request or persistence, asset/hash mismatch, missing security header, broken fallback, unmeasured performance claims, or mismatch between the deployed URL and reviewed commit. Always block accuracy and guaranteed-fit claims until physical evidence passes, even when every software check is green.

Legacy model-release and GCP readiness scripts remain historical controls outside this browser-client release chain.
