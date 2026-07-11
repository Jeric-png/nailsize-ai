# Goal Evidence Ledger

This ledger links goal claims to current, reproducible evidence. A checkbox is complete only when its evidence exists and passes.

| Area        | Claim                                                                              | Evidence                                                                        | Status                                              |
| ----------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------- |
| Repository  | Source repository and monorepo foundation exist                                    | Git history; root workspace configuration                                       | Complete                                            |
| Design      | Stitch workflow is implemented at the two required responsive widths               | `DESIGN.md`; Playwright screenshot baselines; `core-flow.spec.ts`               | Frontend workflow complete                          |
| Privacy     | Current application has no persistent image/result path and log fields fail closed | `docs/privacy-and-threat-model.md`; `test_logging.py`; `session.test.ts`        | Foundation complete; staging verification pending   |
| Calibration | Current API cannot return millimetres without validated inference                  | `test_api.py::test_measurement_never_returns_width_without_validated_inference` | Complete for current API path                       |
| Accuracy    | Required real-world accuracy gates pass                                            | Participant-disjoint validation report                                          | Blocked on study data                               |
| Deployment  | Versioned frontend, API, edge-security, and identity contracts pass local checks   | `vercel.json`; `infra/bootstrap`; `infra/platform`; Cloud Run recovery manifest | Configuration ready; deployment/load tuning pending |
| Operations  | Observability resources and required inputs fail closed before cloud provisioning  | `infra/observability`; `docs/observability.md`; Terraform test output           | Configuration ready; cloud evidence pending         |

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

## 2026-07-12 privacy-safe observability contract

- The API now emits allow-listed structured events for cold-start readiness, request status and total latency, decode/quality stage latency, retake codes, and model/chart versions. Server-generated UUIDs correlate events without reflecting caller-provided identifiers.
- Tests parse emitted JSON, verify the expected stages and response correlation, and retain the existing fail-closed sensitive-field checks. Provisioned log-based metrics, Cloud Run saturation data, dashboards, retention, and alerts remain deployment gates.
- GitHub CI run [29162325250](https://github.com/Jeric-png/nailsize-ai/actions/runs/29162325250) passed all five jobs for observability commit `7e655c6`.

## 2026-07-12 reproducible load-gate harness

- The staging load tool sends bounded-concurrency multipart captures, records only status and elapsed time, and reports aggregate throughput plus nearest-rank p50/p95/p99 latency. HTTPS is mandatory except for explicitly enabled localhost runs.
- It exits non-zero on any non-200/transport failure or when the plan's 2s/5s/10s latency gates fail. Mock-transport tests prove the concurrency ceiling, multipart contract, percentile calculation, error accounting, and release decision without claiming deployed performance.
- GitHub CI run [29162388591](https://github.com/Jeric-png/nailsize-ai/actions/runs/29162388591) passed all five jobs for load-harness commit `9424cdb`.

## 2026-07-12 integrated calibrated measurement pipeline

- The production endpoint now connects validated capture calibration to hand detection, semantic fingertip crops, ONNX segmentation, mask quality, crop-to-source-to-card-plane contour projection, transverse-chord measurement, transformed boundary uncertainty, confidence gating, and immutable chart mapping.
- Crop pixels are never treated as physical pixels. Synthetic tests verify the projection scale and source-normalized overlay contour; pipeline tests verify complete semantic measurement sets and typed rejection for missing hands, low confidence, unsafe projection, and missing boundary-error evidence.
- Response validation makes partial success structurally invalid: retakes require an issue and zero measurements, while success requires exactly the expected digit order and no issues. An HTTP integration test proves the ready success branch. This is implementation evidence only; no accuracy claim is made until representative consented data produces approved weights and boundary metrics.
- GitHub CI run [29162576289](https://github.com/Jeric-png/nailsize-ai/actions/runs/29162576289) passed all five jobs for integrated-pipeline commits `5204417` and `a407d36`, including 16 Playwright scenarios and 93%+ measured Python coverage.

## 2026-07-12 fail-closed runtime image contract

- The non-root Python 3.12 image installs MediaPipe/OpenCV's native EGL, GL, GLES, and GLib requirements plus the pinned landmarks extra, then copies only the hand-landmarker task and selected nail-segmentation ONNX runtime artifacts.
- Docker build fails when either artifact is absent or empty. Repository tests lock the narrow copy allowlist so research data/tooling cannot enter the image. CI generates a clearly named synthetic graph, builds the container, starts it with matching version/checksum/boundary configuration, and requires `/ready`; the fixture is never uploaded or used as accuracy evidence. A production image still cannot be approved until validated ONNX weights pass the same smoke.
- GitHub CI run [29162862065](https://github.com/Jeric-png/nailsize-ai/actions/runs/29162862065) passed all six jobs for commit `b65fe0d`, including the container build and live readiness smoke. Two preceding failed runs exposed and then verified the required native OpenCV dependencies, demonstrating that the smoke checks runtime startup rather than image construction alone.

## 2026-07-12 participant-clustered accuracy-report contract

- The dependency-light `nailsize-accuracy-report` CLI accepts participant-disjoint JSONL observations and produces versioned, deterministic JSON containing overall metrics, 95% participant-clustered bootstrap intervals, dataset-size checks, and explicitly declared adequately sampled cohort results.
- It enforces the plan's 200-participant/2,000-nail holdout minimum, all six overall width/size gates, subgroup MAE at most 0.85 mm, and subgroup exact-size accuracy no more than five percentage points below overall. Missing declared cohorts, duplicate declarations, invalid observations, insufficient bootstrap iterations, and any failed gate prevent a passing report.
- Cohort adequacy is deliberately supplied by the approved study review rather than inferred from an invented count threshold. Fifteen focused evaluation/reporting tests pass on synthetic records; this verifies calculations and fail-closed behavior only, not real-world accuracy or fairness.
- A release report must declare at least one adequately sampled cohort for every planned dimension: skin tone, curvature, nail width, and device. Empty or partial fairness declarations cannot pass.

## 2026-07-12 model-card publication contract

- The `nailsize-model-card` CLI refuses publication unless the versioned accuracy report passes its dataset, overall, subgroup, and required-dimension checks.
- Required model evidence includes a lowercase SHA-256 digest, model and dataset versions, intended use, out-of-scope cases, limitations, IoU/Dice plus mean/p95 boundary error, ONNX maximum absolute parity error at or below `1e-4`, and named model-owner, nail-tech, and privacy/security reviews.
- Generated Markdown embeds participant/nail counts, participant-clustered confidence intervals, every adequately sampled cohort result, limitations, and review references. Synthetic tests verify the publication contract only; the model-card checklist remains open until real locked-holdout evidence and reviews are supplied.

## 2026-07-12 product privacy-notice implementation

- The product footer links to a dedicated notice explaining that photos, previews, and measurements live in browser memory; server uploads and decoded buffers are transient; application storage receives no photos or measurement results; logs exclude filenames, pixels, contours, widths, and results; and production uploads cannot enter the separate consented research workflow.
- The notice repeats the prohibition on payment/government-ID reference cards and names a blank ISO ID-1 card as the safe alternative. An E2E accessibility scenario locks the core claims and scans the rendered page. The publication task remains open until this notice is deployed at the public production origin.

## 2026-07-12 operational validation-report contract

- The `nailsize-operational-report` CLI consumes a versioned, image-free private study bundle and reports first-pass and one-retake completion, invalid false acceptance, valid false rejection, repeated-capture differences, and reviewer-declared adequately sampled cohort rejection gaps.
- It enforces the plan's 200-participant minimum and numeric completion/rejection gates, requires participant coverage across all inputs, requires all four planned cohort dimensions, and publishes deterministic participant-clustered 95% bootstrap intervals.
- The plan does not define universal numeric repeatability or subgroup rejection-parity thresholds. The report therefore exposes the measurements and requires named study-review references instead of inventing cutoffs. Synthetic tests validate calculations and fail-closed behavior only; the related study checkboxes remain open pending consented real-world evidence.
- GitHub CI run [29163415282](https://github.com/Jeric-png/nailsize-ai/actions/runs/29163415282) passed all six jobs for commit `9805d1a`, including Linux lint and dependency-light ML coverage, contracts, web, E2E, security, and live container readiness.

## 2026-07-12 in-memory multipart boundary

- The audit found that framework multipart handling could roll uploads above Starlette's default spool threshold to a temporary file before application decoding. The service now sets the spool threshold one byte above a bounded multipart envelope and rejects both declared-length and chunked bodies before that envelope is crossed.
- API regressions exercise an upload above the former 1 MiB threshold and a request beyond the full-body ceiling while tracking every framework spool; neither rolls to disk. Lower-level tests prove excess chunked data is rejected before the chunk reaches multipart parsing.
- This closes the known application-level temporary-file path. The release checkbox remains open until cancellation, timeout, forced termination, Cloud Run telemetry, and platform storage behavior are observed in staging.
- GitHub CI run [29163653051](https://github.com/Jeric-png/nailsize-ai/actions/runs/29163653051) passed all six jobs for commit `b9601d8`, including Linux inference/privacy tests and the live container readiness smoke.

## 2026-07-12 deployment-smoke evidence contract

- The deployment-smoke command validates only exact staging/production HTTPS origins and refuses direct `run.app` targets so release evidence exercises the configured load balancer and edge controls.
- Six checks cover API health, readiness, immutable model identity, exact trusted CORS, untrusted-origin rejection, a fixed non-image `415` response with `no-store`, and Vercel HTML/security headers. Reports allow-list hostnames, status codes, enumerated results, and the expected model version; response bodies and request payloads are never copied.
- The GitHub workflow supports both manual dispatch and reusable `workflow_call`, preserves read-only repository permissions, and retains the safe JSON artifact for 30 days. Real staging/production execution remains pending deployment credentials and immutable revision URLs.
- GitHub CI run [29163868302](https://github.com/Jeric-png/nailsize-ai/actions/runs/29163868302) passed all six jobs for commit `10b24c6`; GitHub also registered `Deployment smoke` as an active workflow.

## 2026-07-12 observability infrastructure contract

- The named inference logger now owns a JSON-only stdout handler with propagation disabled, preventing Uvicorn prefixes from turning structured events into unqueryable text payloads. Every line includes Cloud Logging's recognized `severity` field, while the existing allow-list still rejects photos, filenames, contours, widths, recommendations, and result summaries.
- Terraform pins Google provider `7.39.0` and defines 30-day `_Default` log retention; bounded-cardinality stage, outcome/retake, cold-start, and malformed-upload metrics; Cloud Run request, latency, saturation, concurrency, CPU/memory, startup, billable-time, and version dashboards; four incident policies; and a project-scoped budget.
- Error rate, p95 latency, malformed-upload rate, maximum instances, budget/currency, budget thresholds, and verified notification channels are mandatory inputs. Seven Terraform tests prove valid planning and rejection of unsafe environment, notification, error-rate, instance-cap, budget, and threshold inputs without cloud credentials.
- Local verification passed Terraform formatting, provider-backed validation, and 7 Terraform tests; Ruff formatting/lint; 214 Python/ML tests at 93.34% measured coverage; 24 web tests; TypeScript; ESLint; the Vercel production build; 18 Playwright mobile/desktop flows; and the high-severity dependency audit.
- No Google Cloud resource was created or changed. The related release checkboxes remain open until authorized staging and production plans are reviewed/applied, notification delivery is tested, dashboard time series are inspected, and immutable evidence is recorded.

## 2026-07-12 platform and edge-security infrastructure contract

- `infra/bootstrap` first enables required APIs and provisions the environment-specific Artifact Registry repository plus a dedicated runtime service account with no project-role grants. This permits the validated image to be pushed before the image-dependent `infra/platform` stack creates Cloud Run, a serverless NEG, a global external HTTPS load balancer, managed TLS, HTTP redirection, and Cloud Armor.
- Cloud Run is locked to one request per instance, one warm instance, the load-tested maximum, 2 vCPU, 4 GiB, a 15-second timeout, exact CORS origin, immutable image/model identifiers, load-balancer-only ingress, and a disabled default `run.app` URL. Public IAM grants only `roles/run.invoker`; the network boundary forces internet traffic through Cloud Armor.
- Cloud Armor requires an explicit per-IP threshold and supported interval, emits full backend request logs, begins in caller-selected preview mode, and returns `429` only after reviewed enforcement. Provider-backed tests prove the bootstrap prerequisites and secure boundary, rejecting mutable or cross-environment images, wildcard origins, unapproved environments, and invalid rate intervals.
- Local verification passed formatting, Google provider 7.39.0 validation, two bootstrap tests, and seven platform tests. No Google Cloud resource was created or changed, no domain was pointed, and no rate threshold was inferred. Provisioning, certificate activation, preview-log review, enforcement, IAM inspection, and deployment smoke evidence remain open.
- GitHub CI run [29164498124](https://github.com/Jeric-png/nailsize-ai/actions/runs/29164498124) passed all eight jobs for commit `63139ac`, including separate Linux validation/test jobs for the platform and observability roots, 214 Python/ML tests, contract drift, web checks, security scans, Playwright, and live container readiness.
- GitHub CI run [29164677105](https://github.com/Jeric-png/nailsize-ai/actions/runs/29164677105) passed all nine jobs for bootstrap/runtime split commit `3c5f160`, including separate Linux validation/test jobs for bootstrap, platform, and observability plus the complete application and container suite.

## 2026-07-12 credential-ready release automation contract

- A fail-closed release verifier requires exactly the approved ONNX model, selected-checkpoint export report, metadata, locked-holdout accuracy report, operational report, and deterministically regenerated model card. It verifies the approved checksum/version, exporter provenance, real-study minimum counts, every declared gate and cohort review, repeatability review, and a positive p95 segmentation boundary error before emitting bounded metadata.
- A separate runtime verifier loads the exact released ONNX file through the production `NailSegmentationModel`, which enforces checksum, embedded version, fixed input/output tensors, CPU provider availability, and warm-up inference before the file may enter a container build.
- The manual-only deployment workflow requires a protected staging or production GitHub environment and serializes each environment. Production requires the literal `DEPLOY_PRODUCTION` confirmation and deletion protection. Model release/runtime verification occurs before Google OIDC authentication; Vercel production creation occurs only after backend and observability apply, so a failed backend deployment leaves the previous frontend serving. No service-account JSON key or Vercel CLI is used.
- After protected-environment approval, the Vercel REST gate creates a production deployment from the connected GitHub repository and exact 40-character SHA, then polls only the returned immutable deployment ID. Project, repository, Git source, SHA, and target identity are revalidated on every response; terminal failures fail immediately, only `READY` plus `PROMOTED` passes, and the retained report excludes its access token.
- Every Terraform root now declares a GCS backend, with documented non-overlapping prefixes. Local Terraform 1.15.8 formatting, initialization without a live backend, validation, two bootstrap tests, seven platform tests, and seven observability tests passed. `actionlint` 1.7.9 accepted both deployment workflows. Ruff accepted all ML/inference sources and 20 focused release/runtime/Vercel tests passed.
- Final pre-commit verification passed 236 Python/ML tests at 93.34% measured coverage, 24 web tests, contract drift, TypeScript, ESLint, the Vercel-compatible production build, 18 Playwright mobile/desktop scenarios, 16 Terraform tests, workflow lint, and the high-severity npm audit with zero reported vulnerabilities. The local Docker daemon was unavailable, so container construction remains delegated to the existing required Linux CI job and is not claimed from local evidence.
- GitHub CI run [29165365931](https://github.com/Jeric-png/nailsize-ai/actions/runs/29165365931) passed all nine jobs for release-automation commit `ce274b3`, including Linux release-verifier tests, contract drift, web and E2E checks, security scanning, all three Terraform roots, and the runtime container build plus live readiness smoke.
- No GitHub protected environment, workload identity binding, state bucket, Vercel project, model release, cloud resource, DNS record, or public deployment was created or changed by these source checks. Real model evidence, authorized deployment, smoke results, device passes, and sign-offs remain open.

## 2026-07-12 staging-to-production promotion contract

- Production now requires the numeric ID of a successful `Deploy verified release` staging run for the exact `main` commit, model release tag, model version, and model checksum. The gate runs before Google OIDC authentication and rejects a different workflow/event/branch/SHA, incomplete or failed run, mutable image reference, mismatched deployment identity, unpromoted Vercel result, or incomplete/failed smoke report.
- Promotion evidence cross-checks the staging deployment and smoke artifacts: exact HTTPS frontend/API hosts, digest-pinned container, seven uniquely named passing endpoint/security checks, the deployed frontend bundle's exact direct API binding, and the same immutable model identity. The emitted promotion report retains only bounded identifiers and hostnames.
- Unit/configuration tests validate successful promotion and fail-closed behavior for run, commit, environment, model, Vercel, and smoke mismatches. These tests validate the gate only; no staging environment or production promotion is claimed.
- A read-only GitHub API audit returned zero configured repository environments and zero published releases. Remote environment protection, release assets, cloud identity, and deployment evidence therefore remain absent rather than inferred from the source configuration.

## 2026-07-12 current browser-engine compatibility

- A separate required CI job executes the nine functional, recovery, privacy, keyboard, accessibility, and four-capture/ten-result scenarios across five current Playwright profiles: Android Chromium, iOS WebKit, desktop Chromium, desktop Firefox, and desktop WebKit. Visual baselines remain isolated to the approved Chromium mobile/desktop projects.
- The first 45-test compatibility run exposed two WebKit assumptions. WebKit correctly used the supported original-PNG upload fallback when canvas WebP rewriting was unavailable, and its default link-tab behavior depended on the host full-keyboard-access preference. The suite now verifies PNG fallback plus keyboard focus/activation without weakening Chromium tab-order coverage.
- The corrected local compatibility run passed all 45 scenarios. This is current engine/emulation evidence only; it does not prove the plan's current-and-previous-two branded versions, physical iOS/Android devices, Edge, VoiceOver, or TalkBack, so those release gates remain open.
- Final local verification used Playwright 1.61.1 and passed 251 Python/ML tests at 93.34% measured coverage, 24 web tests, 18 Chromium visual/E2E scenarios, all 45 current-engine scenarios, contract drift, Ruff, ESLint, TypeScript, the production build, workflow lint, 16 Terraform tests, and the high-severity npm audit with zero reported vulnerabilities.
- GitHub CI run [29165801302](https://github.com/Jeric-png/nailsize-ai/actions/runs/29165801302) passed all ten jobs for commit `9d3eda5`, including the new 45-scenario Linux browser-engine gate, the 18-scenario visual/E2E gate, 251 Python/ML tests, contracts, web, security, container readiness, and all three Terraform roots.

## 2026-07-12 deployed frontend/API binding contract

- Deployment smoke schema `nailsize-deployment-smoke@2` adds a seventh mandatory check that parses only same-origin module-script references from the deployed frontend, bounds script count and response size, and requires the same built module to contain both the exact load-balanced API origin and `/v1/measure` path.
- A missing module, cross-origin-only module, stale API origin, failed asset response, oversized asset, or non-JavaScript response fails closed. The retained report records only the check name, bounded result, and status code; it never copies HTML, JavaScript, response bodies, or customer data.
- Production promotion now rejects older six-check smoke artifacts, so the exact staging candidate must prove the new direct-binding contract before Google authentication can begin. Local mock tests prove contract behavior only; staging and production remain unverified until credentialed deployments produce immutable schema-v2 smoke artifacts.
- Fresh local verification passed Ruff formatting/lint, 258 Python/ML tests at 93.34% measured coverage, 24 web tests, contract drift, ESLint, TypeScript, workflow lint, Prettier, and a Vercel-compatible production build with the exact configured staging API origin embedded in the same JavaScript asset as `/v1/measure` and no localhost fallback.
- GitHub CI run [29166150898](https://github.com/Jeric-png/nailsize-ai/actions/runs/29166150898) passed all ten jobs for commit `bb50104`, including the schema-v2 smoke/promotion tests, 258 Python/ML tests, 24 web tests, 18 visual/E2E scenarios, 45 current-engine scenarios, contract drift, security scanning, live container readiness, and all three Terraform roots.

## 2026-07-12 byte-identical container promotion contract

- The deployment audit found that production independently rebuilt the inference container after staging had passed. Even at the same commit and model checksum, mutable build inputs could make that a different artifact, so the workflow did not prove it was deploying what staging tested.
- Staging remains the only environment that runs `docker build`. Production now reads the exact digest from verified staging evidence, authenticates to both environment registries, pulls by digest, retags and pushes into the isolated production repository, and fails unless the resolved destination digest is identical.
- The fail-closed `nailsize-image-promotion@1` report records only the source URI, destination URI, common SHA-256 digest, schema, and pass result. Deployment schema `nailsize-deployment@3` records a null promotion source for staging and the verified staging source URI for production.
- Focused tests cover exact cross-environment promotion and reject digest mismatches, mutable tags, reversed/same repositories, wrong image names, wrong repositories, and non-Artifact-Registry hosts. Configuration tests also require the pull/tag/verify path and the versioned evidence artifact. These are source-level contract checks; no live container copy or cloud deployment is claimed.
- Fresh local verification passed Ruff formatting/lint; 269 Python/ML tests at 93.34% measured coverage; 24 web tests; contract drift; ESLint; TypeScript; the Vercel-compatible production build; 18 Chromium visual/E2E scenarios; 45 current browser-engine scenarios; all 16 Terraform tests and provider validation; workflow lint; Prettier; and the high-severity npm audit with zero reported vulnerabilities. Live cloud promotion remains pending protected-environment credentials.
- GitHub CI run [29166560644](https://github.com/Jeric-png/nailsize-ai/actions/runs/29166560644) passed all ten jobs for implementation commit `8cbbff8`, including 269 Python/ML tests, contracts, web, 18 visual/E2E scenarios, 45 current-engine scenarios, security scanning, all three Terraform roots, and the Linux runtime-container build plus live readiness smoke. A real cross-repository cloud promotion remains unclaimed until protected environments and credentials exist.

## 2026-07-12 source-managed privacy release boundary

- `verify_privacy_release_boundary.py` emits the bounded `nailsize-privacy-release-boundary@1` report and fails closed when the web or inference runtime dependency sets change, a Terraform resource address or structured-log field is not privacy-reviewed, Uvicorn access logging is enabled, optional load-balancer log fields are configured, browser uploads use URL fields, or Vercel permits third-party scripts/CSP reporting.
- The current report covers four web runtime dependencies, eleven inference runtime dependencies, twenty-seven Terraform resources across nineteen types, and eight allow-listed structured-log fields. It records counts and booleans only; it contains no package versions, file contents, environment values, URLs, images, measurements, or result payloads.
- HTTP redirects now strip query strings. Provider-backed Terraform assertions preserve both that setting and complete native load-balancer request-metadata sampling. The application upload path itself remains a fixed body-only `POST /v1/measure` request.
- Focused local verification passed all eighteen privacy-boundary tests plus Ruff formatting and lint. This is source-managed evidence only. Applied GCP logging/IAM, Vercel dashboard integrations, staging failure/cancellation/process-termination telemetry, and the absence of external backups still require credentialed inspection before the release checkbox can close.
- Fresh full verification passed 280 Python/ML tests at 93.34% measured coverage, 24 web tests, contract drift, ESLint, TypeScript, the Vercel-compatible production build, 18 Chromium visual/E2E scenarios, 45 current browser-engine scenarios, all 16 Terraform tests and provider validation, workflow lint, changed-file formatting, and the high-severity npm audit with zero reported vulnerabilities.
- GitHub CI run [29166999426](https://github.com/Jeric-png/nailsize-ai/actions/runs/29166999426) passed all ten jobs for implementation commit `4b80a5e`, including the source-managed privacy verifier, 280 Python/ML tests, security scanning, all browser and infrastructure gates, and the live runtime-container readiness smoke. Its inspected 447-byte `privacy-release-boundary` artifact reports `passed: true`, contains only the documented counts/booleans, and is retained through 2026-08-10.

## 2026-07-12 dynamic ephemeral-runtime contract

- Python audit hooks observe the complete accepted-measurement and malformed-upload paths plus timeout and cancellation while the real decoder cleanup runs. Any write-mode/flag file open or filesystem mutation fails the test; all four paths currently emit zero events, and timeout/cancellation close their upload buffers.
- The Linux runtime-container smoke starts the production image with a read-only root filesystem, every Linux capability dropped, and `no-new-privileges`. The first remote attempt exposed MediaPipe's Matplotlib import trying to create a home cache before readiness. The fix confines that non-customer cache to a 16 MiB, non-executable `/tmp` tmpfs. CI then verifies readiness, submits a malformed multipart upload and requires `415`, stops the process with a one-second grace period, and fails unless the persistent-layer `docker diff` is empty.
- Source tests require every container privacy flag, malformed-request assertion, termination command, and empty-diff check to remain in the required CI job. This proves the checked-in process has no persistent container write path; it does not prove applied cloud telemetry, external integrations, or staging termination behavior, so the release checkbox remains open.
- Fresh local verification passed 286 Python/ML tests at 93.34% measured coverage, 24 web tests, contract drift, ESLint, TypeScript, the Vercel-compatible production build, 18 Chromium visual/E2E scenarios, 45 current browser-engine scenarios, all 16 Terraform tests and provider validation, workflow lint, changed-file formatting, and the high-severity npm audit with zero reported vulnerabilities. The local Docker daemon was unavailable, so the required Linux CI job remains the authority for the live container termination check.
- GitHub CI run [29167304637](https://github.com/Jeric-png/nailsize-ai/actions/runs/29167304637) failed before readiness because the read-only root exposed Matplotlib's implicit home-cache write. Corrected run [29167449608](https://github.com/Jeric-png/nailsize-ai/actions/runs/29167449608) passed all ten jobs for fix commit `6f70cc8`: the Linux image started with its bounded tmpfs, returned the required malformed-upload `415`, terminated, and produced an empty persistent-layer diff. The run also passed 286 Python/ML tests, both browser suites, security scanning, contracts, web, and all infrastructure jobs; its 447-byte privacy-boundary artifact is retained through 2026-08-10.

## 2026-07-12 repository supply-chain controls and live security audit

- Every external action reference across the five GitHub workflows is now pinned to an immutable 40-character commit. A repository test scans every workflow and fails if a future external action uses a branch or tag; local reusable workflows remain allowed.
- Dependabot version updates cover the repository's npm, pip, GitHub Actions, Docker, and Terraform manifests on a weekly schedule, with non-major updates grouped where supported. This provides source-managed update discovery; it does not prove that a proposed upgrade is safe or that an alert has been resolved.
- A read-only GitHub API audit found zero repository environments, zero releases, and zero open non-pull-request issues. Dependabot alerts, code scanning, secret scanning, and vulnerability-alert endpoints were unavailable or disabled. Branch protection returned GitHub's private-repository plan restriction. No repository visibility, billing, security setting, environment, or release was changed.
- The security closure task remains open. A zero-issue tracker is not evidence that severity-1/2 defects do not exist, and the source controls do not replace enabled alert services, deployed-image scanning, staging/production testing, or accountable security and product triage.
- Fresh local verification passed 288 Python/ML tests at 93.34% measured coverage, 24 web tests, contract drift, ESLint, TypeScript, the production build, 18 Chromium visual/E2E scenarios, 45 current browser-engine scenarios, all 16 Terraform tests and provider validation, workflow lint, repository-security lint/tests, formatting, YAML structural parsing, and the high-severity npm audit with zero reported vulnerabilities.
- GitHub CI run [29167762666](https://github.com/Jeric-png/nailsize-ai/actions/runs/29167762666) passed all ten jobs for implementation commit `f273211`, exercising the immutable action references on Linux and passing 288 Python/ML tests, contracts, web, both browser suites, Trivy and npm security checks, the live read-only runtime-container smoke, and all three Terraform roots.

## 2026-07-12 protected GitHub environment audit contract

- `audit_github_environments.py` reads only environment metadata plus variable, secret, and branch-policy names. It never requests secret values and emits no reviewer identities, credentials, configuration values, URLs, or cloud identifiers.
- The fail-closed contract requires exactly development, staging, and production; an empty development boundary; exact reviewed staging/production variable and secret name sets; at least one required reviewer; `main` as the only deployment branch; and production self-review prevention. Five focused tests cover passing configuration, missing/shadow environments, configuration drift, branch/reviewer drift, development secret leakage, redaction, and source/document synchronization.
- The authenticated live audit produced `docs/evidence/github-environment-audit-2026-07-12.json`: all three expected environments are absent, no unexpected environment exists, and `passed` is false. No empty environment, secret, variable, protection rule, or deployment was created. GitHub's current private-repository plan cannot satisfy the complete required reviewer/protection boundary, so the environment task correctly remains open.
- Fresh local verification passed 293 Python/ML tests at 93.34% measured coverage, 24 web tests, contract drift, ESLint, TypeScript, the production build, 18 Chromium visual/E2E scenarios, 45 current browser-engine scenarios, all 16 Terraform tests and provider validation, workflow lint, changed-file Ruff/Prettier checks, JSON evidence equivalence, and the high-severity npm audit with zero reported vulnerabilities.
- GitHub CI run [29168205712](https://github.com/Jeric-png/nailsize-ai/actions/runs/29168205712) passed all ten jobs for implementation commit `d5d4d31`, including the 293-test inference/ML suite, both browser gates, security scanning, contracts, all Terraform roots, and the live read-only runtime-container termination smoke.

## 2026-07-12 production-boundary golden rejection coverage

- The golden manifest now contains ten checksum-locked PNG fixtures and rejects unmanifested/stale PNGs. Its coverage assertion equals every `QualityIssueCode` the service can currently emit, with `UNSUPPORTED_NAIL_CONDITION` explicitly excluded because no validated production emitter exists.
- `wrong-nail-count.png` first passes production reference calibration, then runs the real checksum-validated MediaPipe hand landmarker and requires the production pipeline to return `WRONG_NAIL_COUNT` before segmentation. `outside-default-chart.png` supplies a locked segmentation mask that traverses production crop projection, mask quality, calibrated measurement, uncertainty scoring, and immutable chart mapping before requiring `OUTSIDE_DEFAULT_CHART`.
- These fixtures prove deterministic wiring and fail-closed behavior, not real-world sensitivity, nail-condition recognition, physical accuracy, or participant-level validation. The task remains open until representative labeled condition data supports an approved `UNSUPPORTED_NAIL_CONDITION` design and golden fixture.
- Fresh local verification passed 295 Python/ML tests at 93.50% measured coverage, 24 web tests, contract drift, ESLint, TypeScript, the production build, 18 Chromium visual/E2E scenarios, 45 current browser-engine scenarios, all 16 Terraform tests and provider validation, workflow lint, fixture formatting/checksums, and the high-severity npm audit with zero reported vulnerabilities.
- GitHub CI run [29168545936](https://github.com/Jeric-png/nailsize-ai/actions/runs/29168545936) passed all ten jobs for implementation commit `d6e69c3`, including the expanded 295-test inference/ML suite, both browser gates, security scanning, contracts, all Terraform roots, and the runtime-container privacy smoke.

## 2026-07-12 selected-checkpoint ONNX handoff

- The model tooling now accepts only a checksum-approved selected checkpoint and matching model version, loads it with PyTorch's restricted `weights_only=True` path, validates the recorded training schema, reconstructs the fixed DeepLabV3-MobileNetV3 architecture without fetching weights, and requires strict state-dictionary compatibility.
- ONNX export now writes to a private temporary path, validates the graph and fixed tensor contract, executes CPU ONNX Runtime parity, and publishes the destination atomically only after the configured tolerance passes. A separate atomic JSON report locks the checkpoint and ONNX checksums, model identity, architecture, training counts/loss, tensor shapes, provider, PyTorch version, and measured parity. Failure to publish evidence removes the ONNX output.
- The first focused run exposed that the trainer stored `torch.__version__` as PyTorch's `TorchVersion` object, which the restricted loader correctly rejected. The trainer now serializes a plain string, and a regression test proves newly trained checkpoints round-trip through `weights_only=True` without allow-listing executable globals.
- Fourteen optional-toolchain tests passed, including two real native-to-ONNX Runtime parity exports, checksum/version rejection, atomic-failure cleanup, deterministic training, safe checkpoint loading, and the CPU benchmark harness. The standard suite passed 300 Python/ML tests at 93.50% measured coverage, 24 web tests, contract drift, ESLint, TypeScript, the production build, all 16 Terraform tests and provider validation, workflow lint, the source privacy audit, and the high-severity npm audit with zero reported vulnerabilities.
- This proves the selected-checkpoint handoff and evidence mechanics only. No real study checkpoint was exported, no model accuracy is claimed, and the ONNX checklist remains open until the approved participant-disjoint selection produces reviewed parity evidence at or below `1e-4`.
- GitHub CI run [29172345120](https://github.com/Jeric-png/nailsize-ai/actions/runs/29172345120) passed all ten standard jobs for implementation commit `93acf0d`, including inference/ML, both browser gates, security scanning, contracts, all Terraform roots, and the runtime-container privacy smoke. Dedicated Linux Model Tooling run [29172344559](https://github.com/Jeric-png/nailsize-ai/actions/runs/29172344559) installed the pinned PyTorch/TorchVision/ONNX stack and passed all 14 factory, loss, selected-checkpoint export, safe-load, training, and benchmark tests.

## 2026-07-12 selected-model release provenance

- The release contract now requires the exporter's original `onnx-export-report.json` beside the selected ONNX model, metadata, accuracy report, operational report, and generated model card. Deployment downloads all six assets and the verifier rejects any missing or extra file before cloud authentication.
- Release verification cross-checks the selected checkpoint SHA-256, ONNX SHA-256, immutable model version, fixed DeepLabV3-MobileNetV3 architecture, CPU provider, input/output tensors, positive training counts, finite loss, recorded PyTorch version, parity ceiling, measured parity, and the exact parity value copied into reviewed model metadata. The emitted `nailsize-model-release@2` manifest retains the checkpoint checksum and measured parity for downstream evidence.
- Twenty-six focused tests accept the exact six-file bundle and reject altered/missing/extra report fields, version/checksum/provider/shape changes, invalid training provenance, parity above either the export tolerance or `1e-4` release ceiling, and metadata parity not linked to the export report.
- Fresh local verification passed 317 Python/ML tests at 86.80% measured combined coverage, 24 web tests, contract drift, ESLint, TypeScript, the Vercel-compatible production build, 18 strict mobile/desktop Chromium scenarios, 45 current Chromium/Firefox/WebKit scenarios, all Terraform roots, workflow lint, the privacy release boundary, formatting, and the high-severity npm audit with zero reported vulnerabilities.
- GitHub CI run [29172605715](https://github.com/Jeric-png/nailsize-ai/actions/runs/29172605715) passed all ten jobs for implementation commit `33ab89f`, including 305 dependency-light Python/ML tests at 93.50% coverage, 24 web tests, 18 strict E2E scenarios, 45 browser-engine scenarios, security scanning, contracts, all Terraform roots, and the runtime-container privacy smoke. Dedicated Linux Model Tooling run [29172607521](https://github.com/Jeric-png/nailsize-ai/actions/runs/29172607521) installed the pinned PyTorch/TorchVision/ONNX stack and passed all 40 factory, loss, selected-checkpoint export, release-provenance, safe-load, training, and benchmark tests.
- These checks prove the chain-of-custody mechanism, not the origin or quality of a future submitted checkpoint or study. The model export, accuracy, model-card, and deployment tasks remain open until real approved evidence passes this contract.

## 2026-07-12 repository vulnerability controls

- The authenticated GitHub repository administrator API enabled vulnerability alerts and automated security fixes for the private repository. A subsequent `GET /vulnerability-alerts` returned `204`, and `GET /automated-security-fixes` returned `enabled: true` and `paused: false`.
- The live Dependabot security-alert endpoint returned an empty list, and the repository has zero open product issues. All 13 open pull requests are Dependabot version updates; they are not evidence of a current vulnerability and were not merged merely because their individual CI runs were green.
- GitHub still reports code scanning as not enabled and secret scanning as disabled. Those private-repository controls and branch protection require a supported plan or approved compensating control, so the critical/high issue closure task remains open alongside deployed-artifact scanning and accountable sign-off.

## Evidence rules

- Record exact commands, dates, immutable report paths, and deployed revision identifiers.
- Do not use a mock, synthetic fixture, or passing unit test as evidence of real-world sizing accuracy.
- Do not mark production checks complete using development-only configuration.
