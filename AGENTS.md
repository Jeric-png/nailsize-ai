# Repository Guidelines

## Project Structure & Module Organization

This repository implements the NailSize AI web application as a monorepo:

- `apps/web/`: React, TypeScript, and Vite frontend based on the approved Stitch screens.
- `services/inference/`: FastAPI service for image validation, calibration, and ONNX inference.
- `ml/`: dataset tooling, PyTorch training, evaluation, export, and model cards.
- `packages/contracts/`: generated TypeScript API types and shared enums.
- `tests/e2e/`: Playwright cross-service tests.
- `infra/`: Google Cloud bootstrap, Cloud Run platform, and observability Terraform.
- `docs/`: decisions, validation reports, privacy documentation, and goal evidence.

Keep production photos out of the repository. Test images must be consented, anonymized fixtures under a clearly labelled test-data directory.

## Build, Test, and Development Commands

Preserve these command contracts when adding tooling:

- `npm install`: install JavaScript workspace dependencies.
- `npm --workspace apps/web run dev`: start the frontend locally.
- `npm --workspace apps/web run build`: type-check and build the frontend.
- `pytest services/inference/tests`: run API and computer-vision tests.
- `npm run test:e2e`: run Playwright user-flow tests.
- `npm run lint`: run repository lint checks without rewriting files.

Document new commands in the root `package.json` and README.

## Coding Style & Naming Conventions

Use two-space indentation for TypeScript, JSON, YAML, and CSS; use four spaces for Python. Format TypeScript with Prettier and lint with ESLint. Format and lint Python with Ruff. Use `PascalCase` for React components, `camelCase` for TypeScript functions, and `snake_case` for Python. Name tests `*.test.ts(x)` or `test_*.py`.

Keep API schemas typed and generate frontend contracts from FastAPI OpenAPI. Do not duplicate response shapes manually.

## Testing Guidelines

Every behavior change requires a regression test. Prioritize geometry, size mapping, retake reasons, privacy, and upload validation. Run targeted tests first, then lint, type-check, unit tests, and E2E smoke tests. Never approve sizing changes using segmentation IoU alone; validate millimetre error and physical tip-size agreement.

## Commit & Pull Request Guidelines

Use Lore-style commits: begin with the intent, then add useful trailers such as `Constraint:`, `Rejected:`, `Confidence:`, `Scope-risk:`, and `Tested:`. Pull requests must explain the user impact, list verification performed, link the relevant task, and include screenshots for UI changes. Flag model, chart, privacy, API, or Stitch-design deviations explicitly.

## Security & Privacy

Never commit credentials, customer images, EXIF, measurements, or production payloads. Logs must exclude filenames, contours, widths, sizes, and image content. Production images are transient and must not become training data without separate explicit consent.
