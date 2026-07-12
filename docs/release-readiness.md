# Release Readiness

Release readiness has two distinct gates. A green **client release** proves that the browser-only software is deployable and respects its documented boundaries. It does not satisfy the separate **measurement validation** gate needed for accuracy or fit claims.

## Client release gate

A release candidate is technically ready when all of the following are true for the same commit:

- `npm ci`, lint, typecheck, unit tests, build, and `verify:bundle` pass;
- Chromium E2E and Chromium/Firefox/WebKit compatibility suites pass;
- `npm audit --audit-level=high` and the filesystem Trivy scan have no blocking finding;
- geometry tests cover `23.00 mm` coin-scale conversion, clockwise eight-rim-marker rules, the `120` prepared-image-pixel, `8%`, `6%`, `4.5`-diameter, and `5–25 mm` guardrails, repeat pass/fail, and chart boundaries;
- component/browser tests cover the separate `120 CSS/screen px` rendered-annotation ergonomics guard and one-pixel/eight-pixel rendered CSS keyboard steps, including a high-resolution source;
- image-preparation tests prove source headers over 20 MP or either side over 8192 px are rejected before full decode, while accepted images remain bounded to a 4096-pixel edge and 16 MP;
- session tests prove mandatory coin confirmation and object URL revocation for acceptance, correction/reopen, confirmation withdrawal, and reset; manual review covers replacement and page teardown;
- E2E proves eight local photos produce ten results, exact duplicate repeats and inconsistent measurements block acceptance, copy is text-only, and all observed network requests are same-origin `GET`;
- the protected Vercel deployment and `scripts/verify-web-deployment.mjs` pass for the exact HTTPS URL; and
- manual real-device review passes on current iOS Safari and Android Chrome, including camera/file selection, pointer and keyboard marker placement, results, share/copy, reload, and reset.

Record the commit, GitHub Actions run, immutable Vercel deployment URL, browser/device versions, reviewer, and known limitations in `docs/goal-evidence.md`. Do not record credentials, photos, marker coordinates, or individual results.

## Configuration review

Confirm before production:

- Vercel receives only `VERCEL_TEAM_ID`, `VERCEL_PROJECT_ID`, the production-only `VERCEL_PRODUCTION_URL`, and secret `VERCEL_TOKEN` through the protected deployment environment;
- the project has no API routes, functions, analytics, Speed Insights, replay, error-reporting SDK, or injected integration;
- deployed CSP contains `connect-src 'none'` and scripts are same-origin;
- source maps and legacy API/model provider strings are absent;
- production requires `DEPLOY_PRODUCTION` plus environment approval; and
- the UI consistently identifies the supported Third Series coin, says projected width, discloses that no full perspective correction is performed, explains the two-photo repeat check, and retains the curvature/no-fit disclaimer.

No GCP, Cloud Run, Terraform, domain/capacity/monitoring/billing, Hugging Face, OpenAI, model, or database variable belongs to this release.

## Measurement validation gate

The 0.6 mm two-photo limit demonstrates repeatability only; it is not an accuracy target. The displayed width is the average, while the wider repeat drives conservative size selection. Neither rule proves the marked edges are anatomically correct or that a physical tip fits a curved nail. The official `23.00 ± 0.10 mm` coin tolerance and the absence of full homography/perspective correction are additional physical limitations. The `120 CSS/screen px` rendered-size guard establishes annotation usability only and must never be cited as accuracy validation.

Before making a “validated,” “accurate,” or “fits” claim, complete and independently review the physical protocol in [`data-protocol.md`](data-protocol.md). The evidence must use the deployed workflow and actual tip set, quantify millimetre error and repeatability, report failure/missingness and curvature effects, and justify both the repeat threshold and chart mapping.

`platform-default@1` (18–9 mm for sizes 0–9) is provisional. A nail artist may use the client as a clearly labelled beta measurement aid, but commercial sizing should use an approved artist/manufacturer chart and retain a sizing-kit fallback for borderline or strongly curved nails.

## Stop conditions

Block or roll back the client release for a failed test, unexpected upload/cross-origin request, unreleased object URL, missing security header, injected telemetry, broken real-device flow, or mismatch between deployed URL and reviewed commit. Block accuracy and guaranteed-fit claims whenever physical evidence is missing or fails, even if every software and deployment check is green.

The legacy model-release and GCP readiness scripts do not authorize or block this browser-only client; they remain historical research controls outside the active release chain.
