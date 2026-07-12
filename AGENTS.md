# Repository Guidelines

## Project Structure & Module Organization

The active product is the browser-only React application in `apps/web/`. Geometry, sizing rules, session state, and UI components live under `apps/web/src/`; component and unit tests use `*.test.ts` or `*.test.tsx`. Playwright flows are in `tests/e2e/`, deployment checks are in `scripts/`, and product decisions are documented in `PRD.md`, `DESIGN.md`, `outputs/`, and `docs/`.

`services/inference/`, `ml/`, `packages/contracts/`, and GCP-oriented `infra/` content are legacy research artifacts. Do not reconnect them to the active build or send customer photos to them.

## Build, Test, and Development Commands

- `npm install`: install workspace dependencies; Node.js 22+ is required.
- `npm run dev`: start the Vite app locally.
- `npm run lint`: run ESLint with zero warnings allowed.
- `npm run typecheck`: validate TypeScript without emitting files.
- `npm test`: run Vitest unit/component tests.
- `npm run build`: create `apps/web/dist`.
- `npm run verify:bundle`: reject network/API/model bindings and source maps.
- `npm run test:e2e`: run the core Playwright suite.
- `npm run test:compat`: run the browser compatibility suite.

## Coding Style & Naming Conventions

Use two-space indentation and Prettier formatting. Name React components and types with `PascalCase`, functions and variables with `camelCase`, and constants with `UPPER_SNAKE_CASE` when truly global. Keep geometry pure and deterministic. Reuse capture configuration rather than duplicating group-specific pages.

## Testing Guidelines

Every behavior change needs a regression test. Prioritize Third Series coin confirmation, eight-point rim geometry, `120 px`/`8%`/`6%` calibration limits, the `4.5`-diameter proximity rule, the `0.6 mm` repeatability boundary, size mapping, retakes, object-URL cleanup, keyboard/touch operation, and zero-upload privacy. Run targeted tests first, then the complete command set above. Do not describe repeatability tests as physical accuracy validation.

## Commit & Pull Request Guidelines

Use Lore-style commits: state intent first, then relevant trailers such as `Constraint:`, `Rejected:`, `Confidence:`, `Scope-risk:`, and `Tested:`. Pull requests must summarize user impact, list verification, link the task, and include mobile/desktop screenshots for UI changes. Flag any change to the supported coin, `23.00 mm` scale, geometry thresholds, repeat tolerance, sizing chart, privacy, or Stitch-derived interaction design.

## Security & Privacy

Never commit credentials or customer media. Photos must remain browser-local, must not be uploaded or persisted, and must be released from memory when no longer needed. The active runtime requires no OpenAI, Hugging Face, model, dataset, or application API key.
