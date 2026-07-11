# Goal Evidence Ledger

This ledger links goal claims to current, reproducible evidence. A checkbox is complete only when its evidence exists and passes.

| Area        | Claim                                                                              | Evidence                                                                        | Status                                            |
| ----------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------- |
| Repository  | Source repository and monorepo foundation exist                                    | Git history; root workspace configuration                                       | Complete                                          |
| Design      | Stitch workflow is implemented at the two required responsive widths                | `DESIGN.md`; Playwright screenshot baselines; `core-flow.spec.ts`               | Frontend workflow complete                        |
| Privacy     | Current application has no persistent image/result path and log fields fail closed | `docs/privacy-and-threat-model.md`; `test_logging.py`; `session.test.ts`        | Foundation complete; staging verification pending |
| Calibration | Current API cannot return millimetres without validated inference                  | `test_api.py::test_measurement_never_returns_width_without_validated_inference` | Complete for current API path                     |
| Accuracy    | Required real-world accuracy gates pass                                            | Participant-disjoint validation report                                          | Blocked on study data                             |
| Deployment  | Versioned frontend and API deployment contracts pass local checks                   | `vercel.json`; `infra/cloud-run/service.template.yaml`; `docs/deployment.md`     | Configuration ready; deployment/load tuning pending |

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
- GitHub CI: [run 29159701659](https://github.com/Jeric-png/nailsize-ai/actions/runs/29159701659) passed all five jobs, including checksum-pinned model download and real MediaPipe initialization/inference on Linux.

## 2026-07-12 segmentation-runtime contract

- A generated ONNX graph proves the CPU runtime loads one `1x3x224x160` input and one `1x1x224x160` output, validates embedded model-version metadata, and completes startup warmup.
- Tests reject missing files, checksum mismatches, version mismatches, and invalid crop tensors before measurements are possible.
- Preprocessing uses fixed RGB/ImageNet normalization; postprocessing applies sigmoid probabilities, a fixed threshold, and largest-connected-component cleanup.
- Application readiness now requires initialized hand-landmark and nail-segmentation runtimes; a configured version string alone cannot report ready.
- This verifies the runtime contract only. It is not evidence that a trained nail model is accurate or approved.
- GitHub CI: [run 29159828508](https://github.com/Jeric-png/nailsize-ai/actions/runs/29159828508) passed all five jobs with ONNX Runtime, real MediaPipe Linux initialization, 86 Python tests, contract drift, web, E2E, and security checks.

## 2026-07-12 Stitch-aligned frontend workflow

- Live Stitch MCP retrieval re-verified quality screen `b230e530ded64687b7d0179404a3de69`, processing screen `7f9fa8f92b3b43fabf43a358bfac8199`, mobile results `7c2120dc69554f7fbcab9510ef84455c`, and desktop results `032c6ffdff5244f3a841db78c11d1861` before visual review.
- `npm run typecheck`, `npm run lint`, `npm test`, and `npm run build` passed; the web suite contains 17 unit tests covering image sizing/animation guards, session corrections, typed infrastructure errors, response mapping, and duplicate-request suppression.
- `npm run test:e2e` passed 10 scenarios across 390px mobile and 1280px desktop. The suite proves four accepted captures produce ten results, text-only copy works, a targeted correction preserves other accepted captures, unsupported files recover, and expired in-memory sessions reset safely.
- Sixteen responsive state/width baselines cover landing, preparation, capture, accepted quality, processing, results, unsupported-file recovery, and session recovery. Platform-specific macOS and Linux images (32 files) keep local and GitHub comparisons strict; the second Playwright run passed without updates.
- Axe scans found no critical or serious violations on landing, quality, processing, results, unsupported-file recovery, or session recovery at either width.
- `npm audit --audit-level=high` reported zero vulnerabilities.
- Normalized API contours render only over the browser-local preview. Copy and native sharing contain text measurements only, never photos.
- Browser-decodable static JPEG, PNG, and WebP captures are orientation-normalized, metadata-free WebP uploads capped at a 4096px edge and 16 MP without aspect distortion. Animated files, HEIC/HEIF, oversized encoded sources, and decode failures remain unchanged for the hardened server path; E2E multipart assertions prove the normal browser path uploads the rewritten WebP.
- ADR-005 through ADR-007 record intentional Stitch adaptations for honest processing state, account-free recovery, and calibrated result evidence.
- GitHub CI bootstrap run [29160372615](https://github.com/Jeric-png/nailsize-ai/actions/runs/29160372615) passed all five jobs and generated the checked-in Linux baselines. Strict follow-up run [29160434743](https://github.com/Jeric-png/nailsize-ai/actions/runs/29160434743) verified them without snapshot updates.

## 2026-07-12 deployment-hardening verification

- GitHub CI run [29160620416](https://github.com/Jeric-png/nailsize-ai/actions/runs/29160620416) passed all five jobs for client-side image preparation commit `5486751`, including strict visual baselines, contracts, dependency audit, and Trivy scanning.
- Twenty-six targeted API/configuration/deployment tests prove exact configured origins receive CORS headers, unknown origins do not, wildcard and malformed origins fail startup validation, HTTP is loopback-only in development, staging/production require HTTPS, and required deployment controls remain versioned.
- Repository-wide Python/ML verification passed 103 tests at 92.26% coverage. Ruff formatting and lint, contract drift, TypeScript typecheck, ESLint, 17 web unit tests, the Vercel-compatible production build, 10 Playwright scenarios, and the high-severity npm audit all passed.
- `vercel.json` parsed successfully with seven source-controlled security headers. `infra/cloud-run/service.template.yaml` parsed successfully as YAML and encodes load-balancer-only ingress, concurrency `1`, minimum instances `1`, 2 vCPU, 4 GiB, a 15-second timeout, probes, and immutable runtime metadata.
- `docs/deployment.md` now defines environment isolation, manifest rendering, load-balancer/Cloud Armor requirements, smoke checks, immutable evidence, and frontend/API/model/chart rollback.
- No staging or production resources were changed. Maximum instance count, Cloud Armor enforcement thresholds, billing alerts, public endpoints, and deployment smoke evidence remain pending load-test results and deployment credentials.
- GitHub CI run [29160837235](https://github.com/Jeric-png/nailsize-ai/actions/runs/29160837235) passed all five jobs for deployment-hardening commit `1ce8997`, including Linux runtime initialization, 103 Python/ML tests, strict responsive snapshots, contract drift, build, dependency audit, and Trivy scanning.
- GitHub CI run [29161046835](https://github.com/Jeric-png/nailsize-ai/actions/runs/29161046835) passed all five jobs after moving Playwright artifact handling to the current Node 24 action; successful runs no longer emit missing-artifact or deprecated-runtime annotations.

## 2026-07-12 adversarial-upload verification

- The decoder now requires the decoded image signature, submitted MIME type, and filename extension to agree. JPEG, PNG, WebP, and HEIF-family rules are explicit; a valid PNG disguised as JPEG fails with 415.
- Tests exercise malformed bytes, mismatched MIME/extension combinations, encoded-size overflow, decoded-pixel overflow, a 10-gigapixel decompression-bomb PNG header, animated WebP, corrupted HEIC, unsupported metadata, and static JPEG/PNG/WebP success.
- Early metadata rejection, size rejection, decoder rejection, and success all close the upload handle. The encoded request is held in a mutable buffer and overwritten on every exit; decoded RGB is overwritten when processing completes.
- EXIF orientation is applied before inference and downstream code receives only a copied RGB pixel array, not source metadata. The unused JPEG re-encoding path was removed.
- HTTP tests prove encoded overflow returns 413 with `no-store`; unexpected decoder failure returns a sanitized 500 and neither client filenames nor internal decoder details enter responses or captured application logs.
- Repository-wide verification passed 119 Python/ML tests at 93.64% coverage, contract drift, Ruff, TypeScript, ESLint, 17 web unit tests, the production build, 10 Playwright scenarios, and the high-severity npm audit.
- GitHub CI run [29160985679](https://github.com/Jeric-png/nailsize-ai/actions/runs/29160985679) passed all five jobs for adversarial-upload commit `2402751`, including the Linux decoder/HEIF environment, 119 Python/ML tests, strict visual snapshots, contract drift, build, dependency audit, and Trivy scanning.

## 2026-07-12 frontend-interruption verification

- Quality-screen unmount now aborts the active `fetch` through a screen-scoped `AbortController`; the completion handlers cannot update the discarded screen. A component test proves unmount changes the exact request signal to `aborted`.
- API unit tests prove concurrent same-file submissions share one request, cancellation preserves `AbortError`, cancelled requests leave the deduplication map, offline failures receive a typed recovery code, and the same in-memory file can be retried.
- Playwright simulates unavailable camera capability, cancels the browser picker, then proves the same control still accepts a saved file. A separate scenario aborts the first network request, displays offline recovery, retries, and accepts the unchanged capture.
- The end-to-end completion scenario now erases all object URLs/results and proves `/results` immediately enters privacy recovery. The added assertion exposed a reset/navigation race; an explicit erasing transition now wins before the missing-results guard.
- TypeScript, ESLint, 19 web unit/component tests, and 14 mobile/desktop Playwright scenarios passed after the fix.
- GitHub CI run [29161165178](https://github.com/Jeric-png/nailsize-ai/actions/runs/29161165178) passed all five jobs for frontend-interruption commit `980b13a`, including 119 Python/ML tests, contracts, security scanning, the production build, and all 14 browser scenarios.

## Evidence rules

- Record exact commands, dates, immutable report paths, and deployed revision identifiers.
- Do not use a mock, synthetic fixture, or passing unit test as evidence of real-world sizing accuracy.
- Do not mark production checks complete using development-only configuration.
