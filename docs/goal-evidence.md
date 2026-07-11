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

## 2026-07-12 deterministic quality-gate verification

- Capture-level gates reject blur, localized glare, missing/invalid reference geometry, and excessive perspective before any measurement. Mask-level gates reject insufficient nail pixels, image/crop clipping, enclosed holes, and material convex-boundary deficits.
- Occlusion is a conservative deterministic geometry signal: the larger of enclosed-hole fraction and convex-hull deficit must remain at or below `0.12`. This threshold fails closed but is not evidence of real-world sensitivity or specificity.
- Eight committed PNG fixtures have SHA-256 values in `services/inference/tests/fixtures/golden_quality/manifest.json`; a coverage assertion locks the fixture set to every code emitted by the deterministic capture/mask quality layer.
- Repository-wide inference/ML verification passed 135 tests at 93.94% coverage. `WRONG_NAIL_COUNT` and `UNSUPPORTED_NAIL_CONDITION` are intentionally excluded from this milestone because honest detection requires the representative labeled dataset and validated model path.
- GitHub CI run [29161304340](https://github.com/Jeric-png/nailsize-ai/actions/runs/29161304340) passed all five jobs for quality-gate commit `033f140`, including Linux inference/ML tests, contract drift, security scanning, the production build, and all 14 browser scenarios.

## 2026-07-12 model-evaluation contract

- Dependency-light ML tooling now computes segmentation IoU/Dice and symmetric mean/p95 boundary errors, preventing model selection from relying on overlap alone.
- Physical evaluation computes width MAE, p90 absolute error, signed bias, exact-size rate, exact-or-adjacent rate, and more-than-one-size miss rate. An executable gate applies the exact thresholds in `outputs/plan.md` and passes only when every threshold passes.
- Tests cover shifted boundaries, paired and one-sided empty masks, passing/failing release cohorts, and malformed/non-finite/unpaired inputs. These synthetic checks validate metric definitions only; no model or accuracy task is marked complete.
- GitHub CI run [29161404344](https://github.com/Jeric-png/nailsize-ai/actions/runs/29161404344) passed all five jobs for evaluation-contract commit `1adfc37`, including 145 dependency-light inference/ML tests at 94.45% coverage.

## 2026-07-12 model-build and export tooling

- The optional research environment pins PyTorch `2.13.0`, TorchVision `0.28.0`, and ONNXScript `0.7.1`; default API and CI installs do not pull the heavy training stack.
- A real TorchVision DeepLabV3-MobileNetV3 model emitted the required single-channel logits tensor in a local smoke test. Combined BCE/Dice loss tests prove correct logits score below inverted logits and malformed targets fail.
- The current `dynamo=True` exporter produced a fixed-shape ONNX graph from a synthetic convolutional model, added `nailsize.model_version`, passed ONNX validation, and matched ONNX Runtime output within `1e-4`. Four optional-toolchain tests passed locally with the pinned versions.
- No trained weights were created or approved. Export parity is tooling evidence only; the baseline training, participant-disjoint evaluation, and release model card remain open.
- GitHub CI run [29161496442](https://github.com/Jeric-png/nailsize-ai/actions/runs/29161496442) passed all five default jobs for model-tooling commit `a272813`; heavy optional dependencies remained excluded while their source and documentation passed Linux lint/security checks.

## 2026-07-12 reproducible training runner

- The external JSONL manifest loader requires participant, split, image, and mask provenance; it rejects duplicate image IDs, participant leakage, missing files, absolute paths, and traversal outside the approved research root.
- Image/mask loading produces the exact production `3x224x160` normalized image and `1x224x160` binary mask contracts. Seeds cover Python, NumPy, PyTorch, DataLoader shuffling, and deterministic PyTorch algorithms.
- Three synthetic tests prove preprocessing, split/root enforcement, and repeatable loss/weight updates. A real DeepLabV3-MobileNetV3 CPU dry run trained one batch of two temporary synthetic crops, returned finite loss `1.3563`, and wrote a 44,323,825-byte checkpoint that was deleted with the temporary directory.
- The runner records model configuration, loss history, example count, and PyTorch version. No dataset, checkpoint, or weights were committed, and the baseline-training checklist remains open until approved consented data is supplied.
- GitHub CI run [29161629250](https://github.com/Jeric-png/nailsize-ai/actions/runs/29161629250) passed all five standard jobs after separating the dependency-light 94.45% coverage gate from optional PyTorch execution.
- Dedicated Linux run [29161631910](https://github.com/Jeric-png/nailsize-ai/actions/runs/29161631910) installed the pinned research stack and passed all seven model factory, loss, ONNX export/parity, manifest, preprocessing, and deterministic training-loop tests.

## 2026-07-12 ONNX benchmark harness

- The benchmark runner rejects models outside the fixed production input/output contract, performs configurable warmup, validates every output, and records checksum/provider/host metadata with p50, p95, p99, and mean inference latency.
- Two synthetic ONNX tests prove successful CPU-provider reporting and rejection of an invalid output tensor. These tests validate the harness only; the Cloud Run CPU benchmark checklist remains open until a selected model runs inside the configured 2-vCPU/4-GiB revision.
- GitHub CI run [29161742701](https://github.com/Jeric-png/nailsize-ai/actions/runs/29161742701) passed all five standard jobs for benchmark commit `2cd22c4`. Dedicated Linux run [29161744869](https://github.com/Jeric-png/nailsize-ai/actions/runs/29161744869) installed the pinned stack and passed all nine model/export/training/benchmark tests.

## 2026-07-12 unit-test category audit

- Vitest covers session transitions, targeted correction, typed errors, object-URL cleanup, request deduplication/cancellation, and image preparation. Python tests cover every immutable chart entry and boundary, calibration/measurement geometry, deterministic quality gates, API/annotation schemas, upload normalization, and safe-log field rejection.
- The latest local combined run passed 154 tests; the standard CI run above enforced 94.45% coverage for production and dependency-light ML code. Heavy research modules are separately exercised by the pinned Linux workflow rather than counted as untested default code.

## 2026-07-12 bounded-request contract verification

- Browser measurement requests now have a 16-second deadline, just beyond the configured 15-second service timeout. The timer and caller signal feed one internal abort controller while preserving explicit user cancellation as `AbortError` and mapping deadline expiry to a typed retryable `timeout` error.
- Unit contracts cover typed success and retake bodies, 413, 415, 408, 429, 503, 504, offline failure, deadline expiry, explicit cancellation, deduplication cleanup, and retry of the unchanged in-memory file.
- All 24 web unit/component tests, TypeScript, ESLint, and the Vercel-compatible production build passed. The broad contract checklist remains open because real API success requires selected validated weights, while edge-generated 429/504 behavior requires deployed Cloud Armor/Cloud Run infrastructure.
- GitHub CI run [29162004157](https://github.com/Jeric-png/nailsize-ai/actions/runs/29162004157) passed all five jobs for timeout commit `910e3ef`, including 14 Playwright scenarios and dependency/security scanning.

## 2026-07-12 production/research isolation contract

- A repository-level privacy test parses every production Python module and fails if it imports the research package, PyTorch/TorchVision, common object-storage/database clients, or Sentry. It separately rejects those packages from production runtime dependencies.
- The same contract locks the runtime container to copying only the inference `pyproject.toml` and `app/`, and requires model tooling to remain manually dispatched without artifact download or Google Cloud authentication.
- These controls prove there is no repository path from a production request to training. The checklist remains open until deployed Cloud Run IAM and telemetry are inspected, because source controls cannot prove cloud identity permissions or platform configuration.
- GitHub CI run [29162050166](https://github.com/Jeric-png/nailsize-ai/actions/runs/29162050166) passed all five jobs for privacy-boundary commit `05d34d1`; the inference job executed the new repository contracts in the measured test suite.

## 2026-07-12 persistent-write exclusion contract

- CI statically rejects filesystem-writing calls and temporary-file/database imports in the production Python application. Browser source is separately rejected if it introduces local/session storage, IndexedDB, Cache Storage, persistent-storage management, or beacon payload export.
- These guards complement runtime buffer-zeroing, upload closure, object-URL revocation, safe-log tests, and `no-store` responses. The full checklist remains open until deployed cancellation, timeout, and forced process termination are observed against Cloud Run/Vercel telemetry and storage configuration.
- GitHub CI run [29162139676](https://github.com/Jeric-png/nailsize-ai/actions/runs/29162139676) passed all five jobs for persistent-write exclusion commit `7446f84`.

## 2026-07-12 automated accessibility coverage

- Axe now scans every distinct workflow state represented by the approved Stitch screens: landing, preparation, capture, accepted quality, processing, results, typed upload error, and expired-session recovery.
- Every scan runs at the 390px mobile and 1280px desktop Playwright viewports and fails on critical or serious violations. Expanding coverage exposed an unnamed file input on capture; the control now has a capture-specific accessible name. Manual keyboard, VoiceOver, and TalkBack verification remains open and cannot be replaced by automated scans.
- GitHub CI run [29162095262](https://github.com/Jeric-png/nailsize-ai/actions/runs/29162095262) passed all five jobs for accessibility commit `e6d5128`, including the expanded Axe coverage in both Playwright projects.
- Automated keyboard checks verify visible focus order and Enter activation from landing through preparation to capture. Client-side route changes move focus to the new primary heading for predictable announcement and onward tab order. The hidden file input is programmatically named but removed from sequential focus because the visible upload button owns that interaction.
- GitHub CI run [29162222625](https://github.com/Jeric-png/nailsize-ai/actions/runs/29162222625) passed all five jobs for route-focus commit `0c1b348`, including 16 Playwright scenarios in both viewport projects.

## Evidence rules

- Record exact commands, dates, immutable report paths, and deployed revision identifiers.
- Do not use a mock, synthetic fixture, or passing unit test as evidence of real-world sizing accuracy.
- Do not mark production checks complete using development-only configuration.
