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

## Evidence rules

- Record exact commands, dates, immutable report paths, and deployed revision identifiers.
- Do not use a mock, synthetic fixture, or passing unit test as evidence of real-world sizing accuracy.
- Do not mark production checks complete using development-only configuration.
