# Observability Contract

## Active browser-only release

NailSize Guide deliberately has no application telemetry. It does not send photos, marker coordinates, projected widths, size suggestions, session identifiers, errors, performance traces, analytics events, or usage events to a first- or third-party service.

Vercel serves only static HTML, CSS, and JavaScript. Platform request logs may contain normal asset-request metadata such as time, URL, IP-derived information, and user agent, but selected photos and sizing results are never request bodies. Keep Vercel Web Analytics, Speed Insights, session replay, injected integrations, and client error-reporting SDKs disabled.

## Release evidence

Operational verification is privacy-preserving and synthetic:

- GitHub Actions records build and test status without customer data.
- `npm run verify:bundle` rejects source maps and legacy API/model-provider bindings.
- Playwright observes the sizing flow and fails on any non-GET or cross-origin request.
- `scripts/verify-web-deployment.mjs` checks the generated Vercel URL, security headers, same-origin scripts, forbidden bundle strings, and SPA routing.
- Manual release review records only commit SHA, deployment URL, browser/device version, pass/fail status, and known product limitations.

Do not attach real customer photos, marker positions, measurements, copied summaries, or browser recordings containing them to issues, CI artifacts, logs, or support tickets.

## Incident handling

Treat any unexpected upload, telemetry SDK, third-party script, source map, API route, or persistent browser storage as a release blocker. Disable or roll back the affected deployment, preserve only non-customer technical evidence, and rerun the privacy, bundle, browser, and deployment checks before promotion.

The retained `infra/observability` and Python logging code document the superseded ML/Cloud Run prototype. They are not provisioned, executed, or required by the active release.
