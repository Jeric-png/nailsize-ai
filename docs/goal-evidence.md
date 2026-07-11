# Goal Evidence Ledger

This ledger links goal claims to current, reproducible evidence. A checkbox is complete only when its evidence exists and passes.

| Area        | Claim                                                                              | Evidence                                                                        | Status                                            |
| ----------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------- |
| Repository  | Source repository and monorepo foundation exist                                    | Git history; root workspace configuration                                       | Complete                                          |
| Design      | Stitch IDs and design contract are recorded                                        | `DESIGN.md`; `outputs/plan.md`                                                  | Complete                                          |
| Privacy     | Current application has no persistent image/result path and log fields fail closed | `docs/privacy-and-threat-model.md`; `test_logging.py`; `session.test.ts`        | Foundation complete; staging verification pending |
| Calibration | Current API cannot return millimetres without validated inference                  | `test_api.py::test_measurement_never_returns_width_without_validated_inference` | Complete for current API path                     |
| Accuracy    | Required real-world accuracy gates pass                                            | Participant-disjoint validation report                                          | Blocked on study data                             |
| Deployment  | Vercel frontend production build passes                                            | `npm run build` on 2026-07-11; `vercel.json`                                    | Frontend build complete; deployment pending       |

## 2026-07-11 foundation verification

- `npm run lint`: passed.
- `npm run typecheck`: passed.
- `npm test`: 2 tests passed.
- `npm run build`: passed; Vite production bundle generated.
- `.venv/bin/ruff check services/inference`: passed.
- `.venv/bin/pytest services/inference/tests --cov=services/inference/app`: 21 tests passed; 93% coverage.
- `npm run test:e2e`: 4 Chromium tests passed across 390px and 1280px projects; no critical or serious axe findings.
- Visual inspection: capture layouts preserve the approved sharp, structural clinical wireframe language at both target widths.
- GitHub CI: [run 29159062823](https://github.com/Jeric-png/nailsize-ai/actions/runs/29159062823) passed all web, inference, contract-drift, E2E, dependency-audit, and Trivy filesystem-scan jobs for commit `bb8c71f`.

## 2026-07-12 calibration verification

- `.venv/bin/pytest services/inference/tests --cov=services/inference/app --cov-fail-under=85`: 56 tests passed; 94% coverage.
- Synthetic references prove known ISO ID-1 dimensions after frontal and projective transforms and after JPEG quality-28 compression.
- Rejection tests cover missing, cropped, wrong-aspect, unstable/steep reference geometry, blur, localized glare, undersized nail masks, and cropped nail masks.
- Rotated synthetic nail masks prove PCA axis estimation and transverse chord widths at 0°, 23°, 67°, 90°, and 135°.
- Calibrated-width tests prove scale and segmentation-boundary error propagation and deterministic confidence thresholds.
- API tests prove valid reference geometry still returns `LOW_CONFIDENCE` with no measurements until validated segmentation is available.
- GitHub CI: [run 29159296041](https://github.com/Jeric-png/nailsize-ai/actions/runs/29159296041) passed all five jobs for calibration commit `7ea38e2`.

## 2026-07-12 dataset-tooling verification

- `.venv/bin/pytest ml/tests -q`: 14 tests passed.
- Combined inference and ML verification: 70 tests passed with 93% coverage, exceeding the 85% CI threshold.
- JSON Schema validation proves representative annotations include nail masks, digit labels, axes, lateral boundaries, quality codes, physical widths, best-fit sizes, and annotator provenance.
- Deterministic participant-level split tests prove one participant cannot appear in more than one dataset partition.
- Annotation-quality tests cover validation failures, Dice overlap, symmetric boundary distance, digit and quality-code agreement, Cohen's kappa, width disagreement, and pairwise agreement reports.
- No real participant data, trained-model metrics, or inter-annotator study results are claimed by these tooling tests.
- GitHub CI: [run 29159473072](https://github.com/Jeric-png/nailsize-ai/actions/runs/29159473072) passed all five jobs for dataset-tooling commit `992f321`.

## 2026-07-12 hand-landmark verification

- MediaPipe `0.10.35` loaded Google's official float16 Hand Landmarker task bundle in image mode and returned no detection for a blank RGB image as expected.
- The downloaded task bundle matched SHA-256 `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`; the checksum-pinned fetch script reproduces the build input without committing the binary.
- Geometry tests prove explicit capture types produce the expected thumb-only or index/middle/ring/pinky semantic order for both sides.
- Crop tests prove fixed tensor shape, source-coordinate mapping, boundary clipping detection, and rejection of incomplete or degenerate landmarks.
- MediaPipe's handedness classification is retained only as diagnostic metadata; it cannot override the submitted left/right capture type.

## Evidence rules

- Record exact commands, dates, immutable report paths, and deployed revision identifiers.
- Do not use a mock, synthetic fixture, or passing unit test as evidence of real-world sizing accuracy.
- Do not mark production checks complete using development-only configuration.
