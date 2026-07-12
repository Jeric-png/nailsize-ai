# NailSize Guide Product Requirements

## 1. Product summary

NailSize Guide is a mobile-first web application that helps customers estimate the projected planar width of all ten fingernails for preliminary press-on nail sizing. It uses guided manual annotation and a current Third Series Singapore 50-cent coin as a local scale reference, entirely in the browser. It does not use a nail dataset, AI model, image API, backend, account, or image storage.

Status: coin-calibrated browser client implemented. Fresh local automated verification, GitHub CI, staging, real-device review, physical accuracy, and tip-fit validation remain separate release gates.

## 2. Problem and users

Customers ordering premade nail sets often do not know which tip size fits each finger. Nail artists need a consistent set of measurements without requiring customers to visit in person.

Primary users:

- customers completing a guided sizing session on a phone;
- nail artists receiving the resulting widths and provisional size suggestions.

## 3. Goals

- Produce a repeatable projected-width estimate for every nail using materials commonly available at home.
- Keep selected photos and measurements on the customer’s device.
- Detect unstable captures through independent repeats instead of presenting false confidence.
- Run as a fast, free-hostable static web application on Vercel.
- Clearly separate software correctness from physical accuracy and fit claims.

## 4. Non-goals

- Automatic nail detection, segmentation, or AI classification.
- Curved-surface width measurement or guaranteed press-on fit.
- Accounts, order management, payments, galleries, analytics, or stored sessions.
- Training-data collection or server-side image processing.
- Final visual styling; interaction and visual decisions are governed by [`DESIGN.md`](DESIGN.md).

## 5. Required user flow

1. Explain the method, privacy boundary, and limitations.
2. Require the user to confirm that the reference is the current Third Series Singapore 50-cent coin showing the Port of Singapore and a large `50` with `CENTS`. Reject older, commemorative, damaged, or foreign coins.
3. Guide four capture groups: left fingers, left thumb, right fingers, and right thumb.
4. Require two independently repositioned photos for every group, for eight photos total. Reject an exact reuse of the first normalized image, while clearly treating this as a duplicate guard rather than proof of physical movement.
5. For each photo, require the user to place eight markers clockwise around the complete coin rim.
6. Lock calibration, then require left and right sidewall markers for every expected nail.
7. Compare each nail’s two readings. Accept only when the difference is at most `0.6 mm`; otherwise request a targeted group retake.
8. Show all ten projected widths and provisional tip sizes, with text-only copy/share and an erase action.

## 6. Measurement contract

Method identifier: `guided-sg50-coin-v1`.

- The only supported reference is the Third Series Singapore 50-cent circulation coin. Its official diameter is `23.00 mm` with a `±0.10 mm` tolerance. The app uses the nominal `23.00 mm` value.
- Eight clockwise rim markers are converted to prepared-image pixel coordinates. Four opposite-marker diameters establish the local pixel scale; their median is used for conversion.
- Calibration fails closed when the coin is smaller than `120 px` in prepared-image/source-coordinate space, opposite diameters differ by more than `8%`, opposite-pair centres differ by more than `6%` of the median diameter, the rim is incomplete, or markers are not clockwise and evenly distributed.
- Coin confirmation also fails when the marked coin appears smaller than `120 CSS/screen px` in the rendered annotation view. This separate threshold keeps rim marking usable on the current display; it is not evidence of physical measurement accuracy.
- Each measured nail must be within `4.5` coin diameters of the reference and yield a plausible `5–25 mm` span.
- The coin and nails must lie flat on the same surface and the phone must be directly overhead. The method rejects obvious tilt through oval/centre checks; it does not compute a full homography or correct arbitrary perspective.
- Displayed width is the average of the two readings, rounded to `0.1 mm`.
- Sizing uses the wider reading so the recommended tip is not narrower than either accepted observation.
- The provisional `platform-default@1` chart maps size `0 = 18 mm` through size `9 = 9 mm`; the nail artist must approve or replace it with the actual supplier chart.
- `0.6 mm` is a repeatability rule, not an accuracy bound or fit guarantee.

## 7. Privacy, safety, and accessibility

- Accept JPEG, PNG, and WebP files up to 12 MB.
- Read supported image headers before full decoding and reject a source over 20 MP or with either side over 8192 pixels. Decode, orient, downscale accepted sources to a maximum 4096-pixel edge and 16 MP, and re-encode as JPEG in the browser; reject normalization failures.
- Compare an in-memory SHA-256 fingerprint of each normalized repeat and reject exact duplicate pixels; discard the fingerprint with the photo.
- Never upload, persist, log, or use photos or measurements for training.
- Revoke object URLs on replacement, retake, acceptance, reset, and teardown.
- Support pointer, touch, and keyboard marker placement with visible focus and at least 44-pixel interactive targets. Arrow keys move a focused marker by one rendered CSS pixel, or eight rendered CSS pixels with Shift; keyboard steps must not be scaled as prepared-image source pixels.
- Label every result as a projected width and retain the curvature/no-fit disclaimer.

## 8. Technical architecture

- React 19, TypeScript, React Router, and Vite.
- Pure client-side geometry and in-memory session state.
- Vitest and Testing Library for unit/component coverage.
- Playwright for Chromium, Firefox, WebKit, mobile layouts, privacy assertions, and complete flows.
- Static Vercel hosting with SPA rewrites, same-origin scripts, and `connect-src 'none'` so runtime requests are disabled.
- No application environment variables or runtime secrets. GitHub deployment environments need only Vercel project identifiers, a production-only protected URL, and a protected deploy token.

## 9. Acceptance criteria

- Eight valid local photos can produce ten results without any non-GET or cross-origin request.
- Reusing the exact normalized first photo cannot satisfy the independent-repeat requirement.
- An inconsistent repeated reading blocks results and preserves unaffected accepted work.
- Reset, reload, or close removes the in-memory session; copy/share contains text only.
- Lint, typecheck, unit, build, bundle audit, Chromium E2E, cross-engine compatibility, dependency audit, and deployment smoke checks pass for the release commit.
- Current iOS Safari and Android Chrome receive a manual real-device review.
- Marketing does not claim validated accuracy or fit until the physical study in [`docs/data-protocol.md`](docs/data-protocol.md) passes.

## 10. Success and release boundaries

The software milestone succeeds when the static client and protected Vercel release path meet the acceptance criteria. Product validation is a separate milestone: a nail professional must approve the physical tip chart and a controlled study must quantify measurement error, repeatability, retake rate, and actual tip agreement. Until then, NailSize Guide is a clearly labelled projected-width beta with a physical sizing-kit fallback.

## 11. Calibration references

The coin specification and identifying design are sourced from the [Singapore Currency Act legal specification](https://sso.agc.gov.sg/SL/CA1967-S347-2013?ProvIds=Sc-&ValidDate=20130611) and the [Monetary Authority of Singapore Third Series coin release](https://www.nas.gov.sg/archivesonline/data/pdfdoc/20130228006/press_release.pdf).
