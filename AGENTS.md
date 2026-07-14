# Repository Guidelines

## Project Structure & Module Organization

The active product is the browser-only React app in `apps/web/`. UI and session code live in `apps/web/src/`; automatic coin detection, ONNX inference, mask decoding, calibration, and sizing live in `apps/web/src/vision/`. Pinned model/runtime assets are under `apps/web/public/models/` and `apps/web/public/ort/`. Unit/component tests use `*.test.ts` or `*.test.tsx`; Playwright flows are in `tests/e2e/`, deployment checks in `scripts/`, and product contracts in `PRD.md`, `DESIGN.md`, `outputs/`, and `docs/`.

`services/inference/`, `ml/`, `packages/contracts/`, and GCP-oriented `infra/` are legacy research. Do not reconnect them or send customer photos to them.

## Build, Test, and Development Commands

- `npm install`: install dependencies; Node.js 22+ is required.
- `npm run dev`: start Vite locally.
- `npm run lint`: run ESLint with zero warnings.
- `npm run typecheck`: validate TypeScript.
- `npm test`: run Vitest and script tests.
- `npm run build`: create `apps/web/dist`.
- `npm run verify:bundle`: audit the manifest, forbidden bindings, and pinned model/WASM hashes.
- `npm run test:e2e` / `npm run test:compat`: run core and cross-browser Playwright suites.

## Coding Style & Naming Conventions

Use two-space indentation and Prettier. Use `PascalCase` for React components/types, `camelCase` for functions/variables, and `UPPER_SNAKE_CASE` only for true globals. Keep calibration and sizing pure, deterministic, versioned, and fail-closed. Preserve the automatic `/instant` flow and the guided `/prepare` fallback as separate method contracts.

## Testing Guidelines

Every behavior change needs a regression test. Prioritize model/hash mismatch, fixed tensor shapes, preprocessing/postprocessing, coin-ellipse guards, five-nail ordering, uncertain-mask review, manual correction, cleanup, zero-upload privacy, and two-photo results. Retain guided tests for eight-point calibration, repeatability, retakes, and keyboard/touch operation. Run targeted tests first, then the complete command set. Never describe software tests, model confidence, or the `0.6 mm` repeat gate as physical accuracy validation.

## Commit & Pull Request Guidelines

Use Lore-style commits: intent first, then useful trailers such as `Constraint:`, `Rejected:`, `Confidence:`, `Scope-risk:`, and `Tested:`. PRs must summarize user impact, list verification, link the task, and include mobile/desktop screenshots for UI changes. Flag changes to the coin, `23.00 mm` scale, model/hash/license, thresholds, chart, privacy, or method version.

## Security & Release Boundaries

Never commit credentials or customer media. Photos remain browser-local and in memory; only same-origin static assets may be fetched. No application API key is required. The automatic beta is not production-deployed: model distribution/legal review and representative physical sizing validation are mandatory before promotion. Its under-90-second goal is unvalidated until measured on named phones.
