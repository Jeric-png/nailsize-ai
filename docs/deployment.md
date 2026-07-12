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

The repository root contains `vercel.json`. Create separate staging and production Vercel projects, connect both to `Jeric-png/nailsize-ai`, and keep the project root at the repository root. The committed `git.deploymentEnabled.main=false` setting disables automatic deployments from `main` so production pushes cannot bypass GitHub environment approval; other branches may still receive previews. Configure:

- Build command: `npm run build`
- Output directory: `apps/web/dist`
- Node.js: 22
- `VITE_INFERENCE_API_URL`: the matching stable load-balanced HTTPS API origin

Pull requests may receive preview deployments. Production deployments must be created by the protected GitHub workflow after staging smoke, accessibility, privacy, and cross-browser checks pass.

The deployment workflow does not install or invoke the Vercel CLI. After protected-environment approval, it calls the official `POST /v13/deployments` endpoint with the connected GitHub repository ID and exact `GITHUB_SHA`, then polls that immutable deployment ID. It refuses to continue unless the project, repository, SHA, production target, `READY` state, and `PROMOTED` substate all still match. Store a narrowly scoped Vercel access token as the protected environment secret `VERCEL_TOKEN`; store project/team/repository identifiers as environment variables. The resulting evidence contains deployment IDs and hostnames, never the token.

Deploy staging first. A production dispatch must supply the successful staging workflow run ID for the same commit, model version, and model checksum. Before cloud authentication, the workflow downloads that run's `deployment-evidence-staging` and `deployment-smoke-staging` artifacts and independently verifies the run identity, digest-pinned image, promoted staging Vercel deployment, endpoint hosts, and exact seven passing smoke checks. A different commit/model, failed run, incomplete artifact, or expired artifact prevents production deployment. Promote within the 30-day evidence-retention window. Production pulls the verified staging image by digest, retags and pushes those exact bytes into the environment-isolated production repository, then fails unless the resolved destination digest is identical. It never rebuilds the production container.

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

Cloud provisioning is deliberately ordered to avoid a fresh-project dependency cycle:

1. Apply `infra/bootstrap` to enable required APIs and create the environment-specific Artifact Registry repository plus role-less runtime identity.
2. In staging, build the validated container, push it to that repository, and resolve its immutable repository digest. For production, copy the staging-tested digest into the production repository without rebuilding it.
3. Apply `infra/platform` with that exact digest-pinned URI. The stack rejects images from another environment or repository.
4. Apply `infra/observability` after the service and verified notification channels exist.

`infra/platform` provisions the Cloud Run service and an isolated ONNX benchmark job, a serverless NEG, a global external HTTPS load balancer, a Google-managed certificate, HTTP-to-HTTPS redirection, full backend request logging, and a Cloud Armor per-IP throttle. Cloud Run uses load-balancer-only ingress, disables its default service URL, and locks concurrency, timeout, CPU, memory, warm capacity, probes, and immutable model metadata. The benchmark job uses the identical digest-pinned image and model, Gen2, 2 vCPU/4 GiB, one task, zero retries, and no network or persistence dependency. Every environment, domain, digest, capacity, and rate-limit value is required; the stack does not invent deployable defaults.

`infra/cloud-run/service.template.yaml` remains a reviewable equivalent for manual recovery. It now carries the same disabled-default-URL boundary as Terraform.

Render and inspect the manifest only after every value is known:

```sh
export SERVICE_NAME=nailsize-staging-inference
export SERVICE_ACCOUNT_EMAIL=nailsize-staging-runtime@PROJECT_ID.iam.gserviceaccount.com
export IMAGE_URI=REGION-docker.pkg.dev/PROJECT_ID/nailsize-staging-inference/inference@sha256:IMAGE_DIGEST
export DEPLOYMENT_ENVIRONMENT=staging
export ALLOWED_ORIGINS=https://STAGING_FRONTEND_HOST
export MODEL_VERSION=MODEL_VERSION
export MODEL_SHA256=MODEL_SHA256
export MAX_INSTANCES=LOAD_TESTED_MAXIMUM
envsubst < infra/cloud-run/service.template.yaml > work/cloud-run-service.yaml
gcloud run services replace work/cloud-run-service.yaml --region REGION --project PROJECT_ID
gcloud run services update "$SERVICE_NAME" --no-default-url --region REGION --project PROJECT_ID
```

For normal provisioning, follow all three infrastructure READMEs. Every Terraform root declares a GCS backend, and the deployment workflow isolates state under `nailsize/<environment>/<root>`. The state bucket must already exist, have versioning and uniform bucket-level access enabled, and grant the deployment identity object access; Terraform cannot safely create the bucket that contains its own state. Never share a state prefix between roots or environments.

Point the API domain's DNS A record to the resulting global address and wait for the managed certificate to become active before smoke testing. The public `allUsers` binding grants only `roles/run.invoker`; load-balancer-only ingress plus the disabled `run.app` URL prevents internet traffic from bypassing Cloud Armor. The runtime service account deliberately receives no project roles because both model assets are bundled in the immutable image.

Begin Cloud Armor rate rules in preview mode, derive per-client thresholds from at least one day of representative staging and abuse-test logs, then submit a separate reviewed plan that changes only the evidence-backed threshold or enforcement switch. The exceed action is `deny(429)`. Do not copy example traffic thresholds into production.

Official references: [Cloud Run ingress](https://docs.cloud.google.com/run/docs/securing/ingress), [Cloud Run YAML](https://docs.cloud.google.com/run/docs/reference/yaml/v1), [Cloud Armor rate limiting](https://docs.cloud.google.com/armor/docs/rate-limiting-overview), [Cloud Run load balancing](https://docs.cloud.google.com/load-balancing/docs/https/setting-up-https-serverless), and [Vercel project configuration](https://vercel.com/docs/project-configuration/vercel-json).

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

## Model release gate

A deployable model is a published, non-prerelease GitHub release whose tag resolves to an ancestor of the deployed `main` commit. The release must contain exactly these assets:

- `nail-segmentation.onnx`
- `onnx-export-report.json`
- `model-metadata.json`
- `annotation-agreement-report.json`
- `dataset-provenance-report.json`
- `holdout-lock-report.json`
- `segmentation-evaluation-report.json`
- `size-calibration-report.json`
- `accuracy-report.json`
- `operational-report.json`
- `model-card.md`

`nailsize-release-bundle` rejects missing or extra assets, placeholder/synthetic version names, checksum mismatches, a regenerated model-card difference, incomplete cohort evidence, fewer than 200 participants, failed provenance/holdout/segmentation/annotation/calibration/accuracy/operational gates, and a nonpositive segmentation boundary error. The dataset-provenance report must be the exact checksum-linked report carried through training and export, declare only approved research-study origin with active research consent, match the training manifest and model dataset identities, contain aggregate counts only, and name research plus production-exclusion reviews. The holdout-lock report must be the exact checksum carried through the checkpoint and export, bind the same manifest and dataset, contain a valid identifier-free test commitment and named review, prohibit selection/tuning access, and exactly match the accuracy report's participant and nail counts. The segmentation report must bind the released model checksum/version and approved holdout commitment, exactly match those same counts, report overlap and boundary metrics with participant-clustered intervals, preserve a validation-selected prediction threshold, and name threshold-selection plus segmentation reviews; model metadata must copy its metrics exactly. The annotation report must match the model dataset version, prove at least 10% double annotation by two independent technicians, contain aggregate agreement metrics, fully adjudicate material disagreements, and name agreement/adjudication reviews. The size-calibration report must use the exact `platform-default@1` chart, match the accuracy holdout's dataset/counts, pass size agreement gates with no unmappable physical widths, quantify physical best-fit margins and curvature cohorts, and name calibration reviews. The bundle also requires the original selected-checkpoint export report and cross-checks its checkpoint/model/dataset/holdout checksums, model version, architecture, CPU provider, fixed tensors, training provenance, parity tolerance, and measured parity against the ONNX bytes and reviewed metadata. The runtime verifier then loads the exact ONNX bytes with `CPUExecutionProvider`, checks embedded model identity and tensor contracts, and performs warm-up inference. These gates validate supplied evidence integrity; they do not make synthetic evidence representative or replace independent study review.

## Credentialed deployment workflow

`.github/workflows/deploy.yml` is manual-only, runs only from `main`, serializes each environment, and uses the matching GitHub protected environment. Production additionally requires the literal dispatch confirmation `DEPLOY_PRODUCTION` and `DELETION_PROTECTION=true`. Configure required reviewers, prevent self-review for production, and restrict both environments to `main` before adding credentials.

Create a dedicated Google deployment service account and GitHub workload identity provider. Bind `roles/iam.workloadIdentityUser` only to the exact environment subjects:

```text
repo:Jeric-png/nailsize-ai:environment:staging
repo:Jeric-png/nailsize-ai:environment:production
```

Also constrain the provider to the repository owner/repository claims. Grant each deployment account only the reviewed permissions needed for the three Terraform roots and GCS state. The staging identity needs Artifact Registry Writer on the staging inference repository. The production identity needs Artifact Registry Reader on that staging repository and Writer on the production inference repository so it can copy the exact tested digest across the environment boundary. Prefer repository-level grants, and never create or store a service-account JSON key. Initial creation of the Google project, billing link, state bucket, DNS records, workload identity pool/provider, deploy identity grants, notification channels, and Vercel projects remains an authorized one-time bootstrap outside this repository.

Define these GitHub environment variables separately for staging and production:

```text
GCP_PROJECT_ID
GCP_REGION
GCP_WORKLOAD_IDENTITY_PROVIDER
GCP_DEPLOY_SERVICE_ACCOUNT
TF_STATE_BUCKET
API_DOMAIN
FRONTEND_ORIGIN
MAX_INSTANCES
RATE_LIMIT_REQUESTS
RATE_LIMIT_INTERVAL_SECONDS
RATE_LIMIT_PREVIEW
DELETION_PROTECTION
MONITORING_NOTIFICATION_CHANNEL_IDS_JSON
ERROR_RATE_THRESHOLD
P95_LATENCY_THRESHOLD_MS
MALFORMED_UPLOADS_PER_MINUTE_THRESHOLD
BILLING_ACCOUNT_ID
MONTHLY_BUDGET_UNITS
BUDGET_CURRENCY
BUDGET_THRESHOLDS_JSON
VERCEL_PROJECT_ID
VERCEL_PROJECT_NAME
VERCEL_TEAM_ID
VERCEL_GITHUB_REPO_ID
```

JSON list variables use Terraform syntax, for example `["projects/PROJECT/notificationChannels/ID"]` and `[0.5,0.8,1.0]`. Begin staging with `RATE_LIMIT_PREVIEW=true`; use only load-tested capacity and evidence-backed alert, budget, and rate values. Store only `VERCEL_TOKEN` as a GitHub environment secret. Workload identity values and resource identifiers are configuration, not private keys.

Before adding any credentials or dispatching a deployment, audit the live GitHub boundary:

```bash
GITHUB_TOKEN="$(env -u GITHUB_TOKEN gh auth token)" .venv/bin/python \
  services/inference/scripts/audit_github_environments.py \
  --repository Jeric-png/nailsize-ai \
  --output work/github-environment-audit.json
```

The audit requires exactly `development`, `staging`, and `production`; exact reviewed variable and secret name sets for staging/production; a required reviewer on each deployment environment; `main` as the only deployment branch; and self-review prevention for production. It records names and counts only—never values, reviewer identities, or credentials—and exits nonzero until every control exists. [GitHub's environment availability rules](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments) limit private-repository environment features and required reviewers by plan; do not replace those controls with empty, unprotected environments. Upgrade to a plan that supports protected private-repository reviewers, or approve a separately designed external deployment-approval control before credentials are introduced.

Dispatch **Deploy verified release** for staging with the published model tag, exact approved model version, and lowercase ONNX SHA-256. After platform apply, the workflow executes the benchmark job and verifies one execution-scoped `nailsize-cloud-run-onnx-benchmark-sample@1` log against the live job definition, execution result, immutable image/model identity, tensor contract, and latency gates. It retains only the aggregate `nailsize-cloud-run-onnx-benchmark@1` report. After that benchmark and the staging smoke job succeed, dispatch production for the same Git SHA and model inputs with that staging run ID plus the literal production confirmation. Production requires the exact staging benchmark report before requesting a Google OIDC token, applies bootstrap, pulls the staging digest, copies it into the production repository, and proves that the destination digest is identical before applying platform and observability state. Deployment schema `nailsize-deployment@3` records the source digest for production and an explicit null for staging; `nailsize-image-promotion@1` records both repository URIs and their shared digest. Only then does the workflow create and verify the exact Vercel production deployment, upload privacy-safe metadata, and call the reusable deployment smoke workflow. This order leaves the previous frontend serving if backend deployment fails. A failed benchmark or smoke job means the release is not accepted evidence, even if infrastructure apply succeeded.

CI also runs `npm run test:compat` against current Playwright Chromium, Firefox, and WebKit engines with Android, iOS, and desktop profiles. Treat this as an early compatibility gate, not as evidence for branded Safari, Chrome, Edge, or physical-device certification. Before production promotion, record current and previous two major versions from the real device/browser matrix required by `outputs/plan.md`.

Official references: [GitHub deployment environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments), [GitHub OIDC](https://docs.github.com/en/actions/reference/security/oidc), [Google authentication action](https://github.com/google-github-actions/auth), [Artifact Registry authentication](https://docs.cloud.google.com/artifact-registry/docs/docker/authentication), [Artifact Registry push and pull](https://docs.cloud.google.com/artifact-registry/docs/docker/pushing-and-pulling), [Vercel Git deployments](https://vercel.com/docs/git), and [Vercel create deployment API](https://vercel.com/docs/rest-api/deployments/create-a-new-deployment).

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
python services/inference/scripts/verify_privacy_release_boundary.py \
  --output work/privacy-release-boundary.json

python services/inference/scripts/deployment_smoke.py \
  --environment staging \
  --frontend-url https://STAGING_FRONTEND_HOST \
  --api-url https://STAGING_API_HOST \
  --expected-origin https://STAGING_FRONTEND_HOST \
  --expected-model-version MODEL_VERSION \
  --output work/deployment-smoke.json
```

The privacy verifier fails on an unreviewed runtime dependency, Terraform resource address, or structured-log field; access logging; optional load-balancer log fields; query-bearing browser transport; or third-party browser scripts. It proves the checked-in release boundary only. The deployment-smoke command requires exact HTTPS origins, refuses the bypassable `run.app` hostname, verifies health/readiness and the immutable model version, checks trusted and untrusted CORS, submits only a fixed invalid byte string to prove typed `415` plus `no-store`, verifies the deployed frontend security headers, and requires a same-origin JavaScript module to contain both the exact load-balanced API origin and measurement path. This proves the deployed Vercel build is bound directly to the matching inference service rather than a stale origin or frontend proxy. Its report contains hostnames, status codes, enumerated outcomes, and the expected model version; it never copies response bodies or bundle contents.

`.github/workflows/deployment-smoke.yml` exposes the same verifier through both `workflow_dispatch` and `workflow_call`. The credentialed deployment workflow calls it after each applied release. It may also be triggered manually for investigation. Link the 30-day JSON artifact in the evidence ledger; workflow source validation is not evidence that a live environment passed.

## Observability and budget

Apply `infra/observability` separately to staging and production only after the Cloud Run service, verified notification channels, approved thresholds, billing account, budget, and remote Terraform state backend are known. The module has no default alert or budget values, so a local validation pass cannot silently become a production policy.

Follow [`infra/observability/README.md`](../infra/observability/README.md) to validate and plan the change. Review the plan before an authorized operator applies it, then verify:

- `_Default` log retention is exactly 30 days;
- each log metric receives only the expected allow-listed JSON fields;
- applied load-balancer logs contain request metadata but no request/response bodies or custom headers;
- Vercel project settings and integrations have analytics, session replay, and crash reporting disabled or independently proven payload-safe;
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
