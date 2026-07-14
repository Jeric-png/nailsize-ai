# Deployment

## Architecture and current release state

NailSize Guide is a static React/Vite client. Automatic coin detection, ONNX nail segmentation, calibration, review, and chart mapping execute in the browser. Vercel serves HTML, JavaScript, CSS, the release manifest, the pinned ONNX model, and the pinned WebAssembly runtime. There is no API route, function, container, database, object store, or inference service.

The release candidate routes `/instant` to the experimental one-photo, one-nail flow. The existing guided client remains the production-safe rollback. A green deployment proves software delivery, privacy boundaries, and artifact identity; it does not prove sizing accuracy or fit.

| Environment | Runtime                  | Purpose                                     |
| ----------- | ------------------------ | ------------------------------------------- |
| Development | Vite on `localhost:5173` | Local implementation and verification       |
| Staging     | Vercel preview           | Approved candidate and device checks only   |
| Production  | Vercel static deployment | Reviewed beta with guided rollback           |

The retained `services/inference/`, `ml/`, `packages/contracts/`, and `infra/` trees are legacy research. Do not provision or deploy them.

## Local verification

Use Node.js 22 or newer:

```sh
npm ci
npm run lint
npm run typecheck
npm test
npm run build
npm run verify:bundle
npm run test:e2e
npm run test:compat
```

`verify:bundle` rejects source maps, telemetry/service-worker bindings, old API paths, and remote OpenAI/Hugging Face inference endpoints. It parses the Vite release manifest, includes lazy chunks in the artifact digest, and verifies the exact ONNX and WASM SHA-256 values. Playwright must prove that runtime traffic consists only of expected same-origin `GET` requests and never contains photo or result data.

## Vercel project and configuration

The Vercel project for `Jeric-png/nailsize-ai` uses the repository root. Committed [`vercel.json`](../vercel.json) defines the build, `apps/web/dist` output, Vite framework, static-asset-safe SPA rewrites, security headers, and `git.deploymentEnabled.main=false` so a push to `main` cannot bypass the protected workflow.

The application has no runtime or build-time secret. Do not add `VITE_INFERENCE_API_URL`, GCP credentials, Hugging Face or OpenAI tokens, model-provider keys, database URLs, or capacity/monitoring/billing variables. The model path and hashes are versioned source contracts, not environment values. Vercel may manage its own OIDC and automation-bypass values; they are not application inputs.

Protected GitHub environments require:

| Name                    | Kind                 | Purpose                              |
| ----------------------- | -------------------- | ------------------------------------ |
| `VERCEL_TEAM_ID`        | Environment variable | Vercel owner/team ID                 |
| `VERCEL_PROJECT_ID`     | Environment variable | Target project ID                    |
| `VERCEL_TOKEN`          | Environment secret   | Narrowly scoped deploy token         |
| `VERCEL_PRODUCTION_URL` | Production variable  | Exact protected `.vercel.app` origin |

Never commit a token. Rotate any credential pasted into chat or logs.

## Promotion gates

Publish only the exact attributed, hash-pinned model described in [`automatic-model-provenance.md`](automatic-model-provenance.md). The public beta must retain the experimental and no-fit-guarantee copy. Long-term licensing interpretation, real-device performance, and physical sizing accuracy remain open independent reviews and must not be presented as completed.

The existing workflow is still named **Deploy guided web** for compatibility. It is manually dispatched from `main`; production additionally requires the exact `DEPLOY_PRODUCTION` confirmation and an environment reviewer. Before it may carry an automatic release, update the workflow naming after its functional checks remain green.

The protected workflow:

1. validates project/team authority and the protected production hostname;
2. runs lint, typecheck, unit tests, build, and bundle verification;
3. installs the pinned Vercel CLI and pulls a static, variable-free project configuration;
4. builds without exposing deployment credentials and proves `.vercel/output/static` is byte-identical to `apps/web/dist` with no functions, middleware, archives, symlinks, or unexpected files;
5. records one digest covering HTML, manifest-listed chunks/styles, and pinned ONNX/WASM assets;
6. deploys the exact prebuilt tree to an explicit preview or staged production target;
7. verifies CLI identity, authenticated project/team/deployment metadata, target, commit, readiness, and every uploaded file through Vercel's API;
8. runs the complete staged production smoke before any alias moves; and
9. promotes only the verified deployment, then proves the protected hostname resolves to that deployment and serves the same digest.

## Runtime smoke contract

`scripts/verify-web-deployment.mjs` must verify:

- HTTPS, a successful `NailSize Guide` shell, and the `/instant` deep route;
- exactly the expected same-origin entry script and stylesheet plus manifest-declared lazy assets;
- exact content types and pinned hashes for `/models/nails_seg_s_yolov8_v1.onnx` and the `/ort/` runtime files;
- no source maps, telemetry, service worker, legacy API, or remote inference binding;
- `connect-src 'self'`, same-origin scripts with `wasm-unsafe-eval`, local worker rules, and committed COOP/COEP/CORP, framing, MIME, referrer, and permissions headers; and
- the same complete artifact digest locally, in the uploaded candidate, in staged production, and after promotion.

The workflows retain their legacy **Guided web deployment smoke** name, but the verifier audits the complete automatic-capable static artifact.

## Browser and platform controls

The CSP permits same-origin static fetches so the beta can load its model and WASM files; it does not authorize photo upload. Because `connect-src 'self'` would also permit a future same-origin endpoint, request-observing tests and project review remain mandatory. Keep Vercel Analytics, Speed Insights, replay, error-reporting SDKs, third-party scripts, and code-injecting integrations disabled.

## Rollback

1. Stop further production dispatches and record the failing deployment URL, commit, method version, and artifact digest without copying photo or result data.
2. Promote or redeploy the last known-good guided/static artifact.
3. Run `scripts/verify-web-deployment.mjs` against the restored URL.
4. Repeat landing, automatic-or-guided capture as applicable, review, results, copy, reset, and real-device checks.
5. Revert the complete method/model/chart version rather than silently changing an existing version.
