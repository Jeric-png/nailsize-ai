# Deployment

## Active architecture

NailSize Guide is a static React/Vite client. Calibration, marker measurement, repeat comparison, and chart mapping execute in the browser. Vercel serves HTML, JavaScript, CSS, and image assets only; there is no API route, function, container, database, object store, or inference service in the active path.

| Environment | Runtime                      | Purpose                      |
| ----------- | ---------------------------- | ---------------------------- |
| Development | Vite on `localhost:5173`     | Local implementation         |
| Staging     | Vercel preview deployment    | Deployment and device checks |
| Production  | Vercel production deployment | Public guided client         |

The retained `services/inference/`, `ml/`, `packages/contracts/`, and `infra/` trees are legacy research work. Do not provision or deploy them for this release.

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

`verify:bundle` rejects source maps, telemetry/service-worker bindings, and built references to the old localhost API, `/v1/measure`, `VITE_INFERENCE_API_URL`, OpenAI, or Hugging Face. Playwright verifies that the sizing flow issues only same-origin `GET` asset and navigation requests.

## Vercel project

Create a Vercel project for `Jeric-png/nailsize-ai` with the repository root as its root directory. The committed [`vercel.json`](../vercel.json) supplies:

- build command `npm run build`;
- output directory `apps/web/dist`;
- Vite framework detection;
- SPA rewrites to `index.html`;
- security headers for every route; and
- `git.deploymentEnabled.main=false`, so a push to `main` cannot bypass the protected manual workflow.

The application has **no runtime or build-time application variables**. Do not add `VITE_INFERENCE_API_URL`, GCP credentials, Hugging Face tokens, OpenAI keys, model paths, database URLs, domain variables, capacity settings, monitoring variables, or billing variables. Vercel CLI may manage `VERCEL_OIDC_TOKEN` and `VERCEL_AUTOMATION_BYPASS_SECRET` as platform-owned system values. Neither is an application input. The byte-identical artifact check proves the platform values did not alter the client output.

The protected GitHub environments need only:

| Name                | Kind                 | Purpose                      |
| ------------------- | -------------------- | ---------------------------- |
| `VERCEL_TEAM_ID`    | environment variable | Vercel owner/team ID         |
| `VERCEL_PROJECT_ID` | environment variable | Target Vercel project ID     |
| `VERCEL_TOKEN`      | environment secret   | Narrowly scoped deploy token |

Production additionally requires `VERCEL_PRODUCTION_URL`, set to the exact authoritative project origin such as `https://nailsize-ai-web.vercel.app`. The workflow does not guess this hostname: the Vercel project-domain API must bind it to the protected project before promotion, and the deployment API must resolve it to the created deployment afterward.

Never commit the token. Rotate any token previously pasted into chat or logs.

## Protected deployment workflow

Run **Deploy guided web** from GitHub Actions on `main` and choose `staging` or `production`. Production additionally requires the exact confirmation `DEPLOY_PRODUCTION` and should require a GitHub environment reviewer.

The workflow:

1. checks the three shared Vercel values and the protected production URL when applicable;
2. runs lint, typecheck, unit tests, build, and bundle verification;
3. installs pinned Vercel CLI `55.0.0` without credentials or install scripts;
4. pulls the selected preview or production project configuration and verifies the protected organization/project IDs, compatible static settings, no application variables, and at most Vercel's managed `VERCEL_OIDC_TOKEN` system key;
5. for production, preflights the protected hostname against Vercel's project-domain API before any alias can move;
6. removes the deploy token from the environment used by `vercel build`;
7. proves `.vercel/output/static` is byte-for-byte identical to the already audited `apps/web/dist`, uses Build Output API v3, allows only bounded Vercel-generated `builds.json` and `diagnostics/` metadata beside it, contains no function output, and records a canonical SHA-256 digest of the served HTML, script, and stylesheet;
8. deploys each file from that exact prebuilt output with an explicit target (`--target=preview` for staging; production uses `--prod --skip-domain` so live aliases do not move yet);
9. verifies the CLI identity and the authenticated REST metadata, including deployment/project/team IDs, release commit, prebuilt state, target, and readiness;
10. retrieves the authenticated deployment file tree and every uploaded file through Vercel's REST API, requires exactly one Vercel-normalized root containing the complete prebuilt tree, rejects archives, functions, middleware, symlinks, extra or missing files, and byte differences, then reproduces the locally recorded application digest; and
11. for production, requires the staged production-target URL to pass the complete unauthenticated runtime smoke test before any alias can move; and
12. promotes only that byte- and runtime-verified production deployment, resolves the public production URL directly back to its deployment ID, and confirms it still serves the same local artifact digest without an authentication bypass.

The deployment smoke verifier requires:

- HTTPS and a successful application shell;
- the expected `NailSize Guide` title;
- same-origin application scripts;
- no source-map or legacy remote-sizing dependency in the script bundle;
- `connect-src 'none'`, the complete committed security-header set, and expected HTML/JavaScript/CSS content types;
- exactly one same-origin application script and stylesheet with no telemetry or service-worker binding;
- the same locally recorded artifact digest in the uploaded candidate, the staged production runtime, and after production promotion; and
- an exact application shell and identical zero-connect CSP at the SPA deep route `/guide/left_fingers/1`.

The **Guided web deployment smoke** workflow can repeat the same check for an exact deployed HTTPS URL.

## Browser and platform controls

`vercel.json` disables runtime connections, restricts scripts to the same origin, allows local blob/data image previews, denies framing, disables object embedding, limits camera access to the app itself, and disables geolocation and microphone permissions. Keep Vercel Web Analytics, Speed Insights, session replay, error-reporting SDKs, third-party scripts, and integrations disabled unless a new privacy review proves they cannot observe photo or result data.

The CSP is a defense-in-depth boundary, not proof by itself. Review the deployed project for dashboard-added scripts or integrations and repeat the real-device capture flow on current iOS Safari and Android Chrome.

## Rollback

1. Stop further production dispatches and record the failing deployment URL and commit without copying photo or result data.
2. Promote or redeploy the last known-good Vercel commit/output.
3. Run `scripts/verify-web-deployment.mjs` against the restored URL.
4. Repeat landing, capture, two-photo agreement, results, copy/share, reset, and real-device camera checks.
5. If geometry or chart behavior changed, revert the complete method/chart version rather than editing an existing version in place.
