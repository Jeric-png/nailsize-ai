# NailSize Guide — Goal Task List

## Goal

Implement, verify, deploy, and physically evaluate the dataset-free guided sizing flow defined in [`plan.md`](plan.md). A green build proves software behavior; it does not by itself prove nail-width accuracy or press-on fit.

## 1. Product and measurement contract

- [x] Replace the unavailable sizing model with browser-local guided measurement.
- [x] Support only the Third Series Singapore 50-cent coin at a nominal `23.00 mm` diameter.
- [x] Require explicit confirmation of the Port of Singapore and large `50`/`CENTS` design; reject older or other coins in guidance.
- [x] Define four capture groups covering all ten nails.
- [x] Require two independent photos per group—eight photos total.
- [x] Reject an exact normalized-image duplicate as the verification photo without claiming that this proves physical repositioning.
- [x] Require eight clockwise coin-rim markers and manual nail-edge placement.
- [x] Convert prepared-image pixel distances to millimetres using the median opposite-marker coin diameter.
- [x] Reject coins under `120 px`, diameter spread over `8%`, centre spread over `6%`, nails beyond `4.5` coin diameters, and implausible `5–25 mm` spans.
- [x] State that the local coin scale does not perform full homography or arbitrary perspective correction.
- [x] Gate every nail on a maximum `0.6 mm` difference between repeats.
- [x] Display average projected width and use the wider repeat for conservative sizing.
- [x] Label results as planar projections with no curved-width or fit guarantee.
- [ ] Have the intended nail artist approve or replace the provisional `18–9 mm` size chart.

## 2. Browser workflow and privacy

- [x] Implement coin confirmation/preparation, four capture groups, retakes, and results.
- [x] Support JPEG, PNG, and WebP files up to 12 MB.
- [x] Support pointer, touch, and keyboard marker adjustment.
- [x] Preserve accepted groups during targeted retakes.
- [x] Copy/share text-only results without photos.
- [x] Keep photos in browser memory and release object URLs on replacement, acceptance, reset, and exit.
- [x] Remove the active measurement API, model dependency, and runtime key requirement.
- [x] Disable production runtime connections with `connect-src 'none'`.

## 3. Automated verification

- [x] Unit-test Third Series coin scale conversion and eight-point rim validation.
- [x] Unit-test marker rules, repeatability threshold, and size mapping.
- [x] Unit-test session transitions and object-URL cleanup.
- [x] E2E-test eight photos producing ten results.
- [x] E2E-test inconsistent repeats and targeted retakes.
- [x] E2E-test unsupported files, reset, copy, responsive layouts, and accessibility checks.
- [x] Assert zero non-GET and zero cross-origin requests in the sizing flow.
- [x] Audit the production bundle for source maps, API endpoints, AI providers, and secret-bound configuration.
- [ ] Confirm the coin-calibrated worktree passes `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, `npm run verify:bundle`, `npm run test:e2e`, and `npm run test:compat` locally.
- [ ] Confirm the same release commit passes the protected GitHub CI and security jobs.

## 4. Vercel release

- [x] Configure the static Vite output, SPA rewrites, and browser security headers in `vercel.json`.
- [x] Configure client-only GitHub CI and manual Vercel deployment workflows.
- [ ] Deploy and smoke-test a staging URL.
- [ ] Review the staging flow on a real phone and desktop browser.
- [ ] Deploy the verified commit to production and record the URL and commit SHA.
- [ ] Confirm production sends no photos or measurements to external origins.

## 5. Physical product validation

- [ ] Agree on devices, conditions, sample size, ground-truth method, and launch thresholds with a nail technician.
- [ ] Test known-width planar targets and Third Series coins across representative phones and camera angles.
- [ ] Compare projected widths with independently measured physical nail widths.
- [ ] Compare recommendations with best-fitting tips from the exact production chart.
- [ ] Report repeatability, absolute error, bias, size-boundary misses, retake rate, and relevant cohorts.
- [ ] Adjust capture guidance, `0.6 mm` repeatability gate, or chart only from documented evidence and rerun verification.
- [ ] Approve accuracy/fit wording, or retain the current experimental projected-width disclaimer.

## 6. Closure

- [ ] Resolve critical/high security findings and blocking product defects.
- [ ] Link final CI, staging, production, privacy, and physical-validation evidence in `docs/goal-evidence.md`.
- [ ] Obtain engineering, product, and nail-artist sign-off.
- [ ] Mark the overall goal complete only when deployment and the intended public claims have supporting evidence.
