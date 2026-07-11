# Deployment

## Environment model

| Environment | Frontend                       | Inference                              | Purpose                                        |
| ----------- | ------------------------------ | -------------------------------------- | ---------------------------------------------- |
| Development | Vite on `localhost:5173`       | Uvicorn on `localhost:8000`            | Local implementation and tests                 |
| Staging     | Vercel preview/staging project | Dedicated Cloud Run staging service    | Integration, privacy, load, and device QA      |
| Production  | Vercel production deployment   | Dedicated Cloud Run production service | Public traffic after every release gate passes |

Never point a preview frontend at the production inference service. Configure a distinct `VITE_INFERENCE_API_URL` and exact `ALLOWED_ORIGINS` value for each environment.

Committed, non-secret templates live in `infra/environments/`. Copy the matching template into the deployment platform and replace every `nailsize.example` or `replace-with-*` value. The API refuses to start with wildcard origins, path-bearing origins, duplicate origins, non-loopback development HTTP origins, or non-HTTPS staging/production origins.

## Vercel frontend

The repository root contains `vercel.json`. Connect `Jeric-png/nailsize-ai`, keep the project root at the repository root, and configure:

- Build command: `npm run build`
- Output directory: `apps/web/dist`
- Node.js: 22
- `VITE_INFERENCE_API_URL`: the matching HTTPS Cloud Run origin

Pull requests should receive preview deployments. Promote to production only after staging smoke, accessibility, privacy, and cross-browser checks pass.

`vercel.json` applies CSP, frame, MIME-sniffing, referrer, browser-capability, and cross-origin isolation headers to every route. Vercel supplies HSTS automatically. Once the production API hostname exists, narrow the CSP `connect-src` directive from generic HTTPS to the exact staging and production API hosts and verify it with the browser console and `curl -I`.

## Cloud Run inference

Build `services/inference/Dockerfile` only after a verified ONNX model is available and its checksum is locked. Required runtime settings:

- 2 vCPU and 4 GiB memory
- one Uvicorn worker and request concurrency `1`
- minimum instances `1`
- application/request timeout of 15 seconds
- exact frontend CORS origin
- request-body and response-body logging disabled
- maximum instances and billing alerts set from the validated traffic model

`infra/cloud-run/service.template.yaml` is the source-controlled service contract. It includes load-balancer-only ingress, concurrency, timeout, CPU, memory, warm capacity, a dedicated service account, startup/liveness probes, and immutable model metadata. It deliberately leaves `MAX_INSTANCES` as a required substitution because an invented value would not prove safety or cost control.

Render and inspect the manifest only after every value is known:

```sh
export SERVICE_NAME=nailsize-inference-staging
export SERVICE_ACCOUNT_EMAIL=nailsize-staging@PROJECT_ID.iam.gserviceaccount.com
export IMAGE_URI=REGION-docker.pkg.dev/PROJECT_ID/nailsize/inference@sha256:IMAGE_DIGEST
export DEPLOYMENT_ENVIRONMENT=staging
export ALLOWED_ORIGINS=https://STAGING_FRONTEND_HOST
export MODEL_VERSION=MODEL_VERSION
export MODEL_SHA256=MODEL_SHA256
export MAX_INSTANCES=LOAD_TESTED_MAXIMUM
envsubst < infra/cloud-run/service.template.yaml > work/cloud-run-service.yaml
gcloud run services replace work/cloud-run-service.yaml --region REGION --project PROJECT_ID
gcloud run services update "$SERVICE_NAME" --no-default-url --region REGION --project PROJECT_ID
```

Use an external Application Load Balancer in front of the service and attach Cloud Armor. The `internal-and-cloud-load-balancing` ingress annotation plus `--no-default-url` prevents public traffic from bypassing the load balancer. Begin Cloud Armor rate rules in preview mode, derive per-client thresholds from staging load and abuse tests, then enforce with a `deny-429` exceed action. Do not copy example traffic thresholds into production.

Official references: [Cloud Run ingress](https://docs.cloud.google.com/run/docs/securing/ingress), [Cloud Run YAML](https://docs.cloud.google.com/run/docs/reference/yaml/v1), [Cloud Armor rate limiting](https://docs.cloud.google.com/armor/docs/configure-rate-limiting), and [Vercel project configuration](https://vercel.com/docs/project-configuration/vercel-json).

## Load validation

Use a synthetic or explicitly approved non-customer capture against staging. Start at the expected concurrency, then rerun at peak plus 20%:

```bash
.venv/bin/python services/inference/scripts/load_test.py \
  --endpoint https://STAGING_API/v1/measure \
  --image /path/to/approved-load-fixture.webp \
  --requests 100 --concurrency 2 \
  --output work/staging-load-report.json
```

The command exits non-zero unless every request returns HTTP 200 and p50 is at most 2 seconds, p95 at most 5 seconds, and p99 at most 10 seconds. The report contains only aggregate timing/status data and endpoint host metadata; it does not embed the image or response bodies.

## Release verification

For each staging or production revision, record the immutable frontend URL, Cloud Run revision, image digest, model checksum, chart version, and CI run in `docs/goal-evidence.md`. At minimum, verify:

```sh
curl --fail --silent --show-error https://API_HOST/health
curl --fail --silent --show-error https://API_HOST/ready
curl --include --request OPTIONS https://API_HOST/v1/measure \
  --header 'Origin: https://EXPECTED_FRONTEND_HOST' \
  --header 'Access-Control-Request-Method: POST'
curl --include --request OPTIONS https://API_HOST/v1/measure \
  --header 'Origin: https://untrusted.example' \
  --header 'Access-Control-Request-Method: POST'
curl --head https://FRONTEND_HOST/
```

The expected origin must receive its exact `Access-Control-Allow-Origin`; the untrusted origin must not. Measurement responses must remain `Cache-Control: no-store`. Confirm the default `run.app` URL is unreachable before promotion.

Use the source-controlled verifier for the reproducible release record:

```sh
python services/inference/scripts/deployment_smoke.py \
  --environment staging \
  --frontend-url https://STAGING_FRONTEND_HOST \
  --api-url https://STAGING_API_HOST \
  --expected-origin https://STAGING_FRONTEND_HOST \
  --expected-model-version MODEL_VERSION \
  --output work/deployment-smoke.json
```

The command requires exact HTTPS origins, refuses the bypassable `run.app` hostname, verifies health/readiness and the immutable model version, checks trusted and untrusted CORS, submits only a fixed invalid byte string to prove typed `415` plus `no-store`, and verifies the deployed frontend security headers. Its report contains hostnames, status codes, enumerated outcomes, and the expected model version; it never copies response bodies.

`.github/workflows/deployment-smoke.yml` exposes the same verifier through both `workflow_dispatch` and `workflow_call`. Run it after each staging deployment and after production promotion. A future credentialed deployment workflow must call this reusable workflow before promotion can succeed; until that workflow exists, trigger it manually and link its 30-day JSON artifact in the evidence ledger.

## Observability and budget

Apply `infra/observability` separately to staging and production only after the Cloud Run service, verified notification channels, approved thresholds, billing account, budget, and remote Terraform state backend are known. The module has no default alert or budget values, so a local validation pass cannot silently become a production policy.

Follow [`infra/observability/README.md`](../infra/observability/README.md) to validate and plan the change. Review the plan before an authorized operator applies it, then verify:

- `_Default` log retention is exactly 30 days;
- each log metric receives only the expected allow-listed JSON fields;
- dashboard panels resolve the exact Cloud Run service and model/chart versions;
- test incidents reach every configured notification channel; and
- budget thresholds notify both the configured channels and authorized project/billing recipients.

Record Terraform state revision, plan review, dashboard ID, alert-policy IDs, notification tests, and budget evidence without copying application payloads. Source validation does not complete the deployment checkboxes by itself.

## Rollback

1. Stop promotion and record the failing revision plus symptom without copying request bodies or results into the incident record.
2. Frontend: promote the last known-good immutable Vercel deployment and repeat header, navigation, and upload smoke tests.
3. API/model: route 100% of traffic to the previous Cloud Run revision. Models are immutable within the image, so never replace model bytes in an existing tag or revision.
4. Size chart: redeploy the last code revision that referenced the previous immutable chart version; never modify an existing chart version in place.
5. Re-run health, readiness, CORS, no-store, representative retake, and frontend E2E checks. Record the restored revisions and evidence before resolving the incident.
