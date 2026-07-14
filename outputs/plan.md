# NailSize Guide — Implementation and Validation Plan

This execution plan implements the product contract in [`../PRD.md`](../PRD.md).

## 1. Goal

Deliver a fast, free-to-host web application that helps a nail artist turn customer-guided photos into repeatable projected nail-width measurements and one clear sizing result per nail: a preliminary best-fit press-on size within the provisional chart or an artist-review flag outside it. The active product must work without a nail dataset, trained model, image API, backend service, or image storage.

The product may claim **guided planar measurement** only. It must not claim curved-surface width, guaranteed fit, or validated accuracy until physical testing supports those claims.

## 2. Product contract

- Support only the current Third Series Singapore 50-cent coin as the scale reference. Require explicit confirmation of the Port of Singapore and large `50`/`CENTS` design because older Singapore 50-cent coins have different dimensions.
- Capture four groups: left fingers, left thumb, right fingers, and right thumb.
- Require two independently taken photos per group—eight photos total. The customer must move the hand and phone between repeats.
- Ask the customer to place eight markers clockwise around the complete coin rim in every photo.
- Ask the customer to mark the visible left and right edge of every expected nail.
- Accept JPEG, PNG, and WebP images up to 12 MB.
- Keep all photos and measurements in browser memory only; never upload or persist them.

## 3. Measurement method

For each photo, convert the eight normalized rim markers to prepared-image pixel coordinates. Pair opposite markers, take the median of their four pixel diameters, and use the nominal `23.00 mm` Third Series coin diameter as the local scale. The legal specification permits `±0.10 mm` manufacturing tolerance.

Reject the calibration when the complete rim is not visible, markers are not clockwise and evenly distributed, the median diameter is under `120 px`, opposite diameters have more than `8%` spread, or opposite-pair centres have more than `6%` spread relative to the median diameter. Keep every measured nail within `4.5` coin diameters of the coin centre and reject projected spans outside `5–25 mm`.

The coin and nails must lie flat on the same surface with the phone directly overhead. This is a local scale estimate with tilt rejection, not a full planar homography or arbitrary perspective correction.

Measure the straight-line distance between each nail’s two projected edge markers. Compare corresponding measurements from the two independent photos:

- `delta ≤ 0.6 mm`: accept the repeat as consistent.
- `delta > 0.6 mm`: show the affected nail and require a targeted retake.

Display the average of the two readings as the projected width. Use the wider reading for conservative default size selection. The provisional chart maps size `0 = 18 mm` through size `9 = 9 mm`; a production nail artist must approve or replace it with the exact supplier chart.

The `0.6 mm` threshold is a repeatability control, not an accuracy guarantee.

## 4. Application architecture

- React 19, TypeScript, Vite, and React Router.
- Pure client-side geometry and session state; no `POST` requests or remote processing.
- Accessible drag/touch/keyboard annotation controls with mobile-first Stitch-derived styling.
- Object URLs released on replacement, retake, acceptance, reset, and session exit.
- Vitest and Testing Library for geometry, state, accessibility, and component behavior.
- Playwright for the full eight-photo flow, retakes, privacy, responsive layouts, and supported browsers.
- Static Vercel deployment with SPA rewrites, same-origin assets, and runtime connections disabled by policy.

Legacy inference, ML, contracts, and GCP infrastructure remain outside the active build and release path.

## 5. Validation strategy

### Automated release gates

- Lint, typecheck, unit tests, build, and bundle privacy audit pass.
- Geometry fixtures prove eight-rim-marker validation, `23.00 mm` pixel-scale conversion, calibration and proximity limits, repeatability boundaries, and chart mapping.
- End-to-end tests complete all four groups and produce one clear sizing result for each of ten nails from eight local photos, with no competing size exposed.
- Browser tests prove inconsistent repeats block recommendations and trigger a targeted retake.
- Network assertions prove zero non-GET and zero cross-origin requests during sizing.
- Built assets contain no source maps, API origins, model providers, or secret-dependent configuration.

### Physical validation before accuracy claims

Automated tests cannot establish real nail accuracy or press-on fit. Before public accuracy claims:

1. Test known-width planar targets and official-tolerance Third Series coins across representative phones, distances, lighting, and camera angles.
2. Compare app readings with technician-measured nail widths using a documented physical method.
3. Compare recommendations with best-fitting tips from the exact supplier chart.
4. Record repeatability, absolute error, systematic bias, boundary misses, retake rate, and device/cohort results.
5. Have a nail technician approve the chart and define acceptable launch thresholds before collecting results.

This validation is a controlled product study, not an ML training dataset. Until it passes, the UI and marketing must retain the projected-width and no-fit-guarantee disclaimer.

The supported reference is documented by the [Singapore Currency Act legal specification](https://sso.agc.gov.sg/SL/CA1967-S347-2013?ProvIds=Sc-&ValidDate=20130611) and the [MAS Third Series coin release](https://www.nas.gov.sg/archivesonline/data/pdfdoc/20130228006/press_release.pdf).

## 6. Deployment

Build the static app with `npm run build`, audit it with `npm run verify:bundle`, and deploy `apps/web/dist` through Vercel. No application runtime variables are required. GitHub deployment environments need only `VERCEL_TEAM_ID`, `VERCEL_PROJECT_ID`, and the secret `VERCEL_TOKEN`.

## 7. Definition of done

Implementation is complete when every local behavior and automated release gate in [`task.md`](task.md) passes. Deployment is complete when staging and production Vercel smoke tests pass. Product validation remains explicitly incomplete until real physical comparison evidence supports the desired accuracy and fit claims.
