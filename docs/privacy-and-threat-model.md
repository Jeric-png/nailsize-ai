# Privacy and Threat Model

## Data flow

1. The browser reads a user-selected photo into an in-memory `File` and object URL.
2. It posts one multipart capture directly to the inference API.
3. The API bounds the complete multipart body in the ASGI receive path, keeps the upload spool above that bound so it cannot roll to disk, then reads at most 12 MB of encoded image data, verifies and decodes at most 25 MP, normalizes orientation, and discards source metadata.
4. Calibration and inference operate synchronously on process memory.
5. The API returns measurements or typed retake issues with `Cache-Control: no-store`.
6. Browser object URLs and results are released on replacement, reset, navigation away, and session completion.

The production path has no database, object storage, queue, image cache, request-body tracing, or training-data export.

## Protected data

- Raw and normalized photos, filenames, and EXIF
- Nail contours, projected widths, recommended sizes, and result summaries
- Any accidental sensitive information visible on a reference card

## Principal threats and controls

| Threat                                   | Control                                                                        | Verification                               |
| ---------------------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------ |
| Sensitive card captured                  | UI prohibits payment/government ID and recommends blank calibration cards      | Content and E2E review                     |
| Oversized/decompression upload           | Streamed body, encoded, decoded, and in-memory spool limits before inference   | API adversarial tests                      |
| MIME spoofing or malformed decoder input | MIME, signature, format, animation, and decoder validation                     | API tests                                  |
| Payload leakage to logs/APM              | Allow-listed structured log fields; access logs disabled                       | Logging tests and production config review |
| Browser persistence                      | In-memory reducer, object URL revocation, no local/session storage             | Unit and E2E tests                         |
| Shared/proxy caching                     | `no-store`, `no-cache`, direct HTTPS API requests                              | Contract tests                             |
| Cross-origin abuse                       | Exact CORS allow-list and deployment-level rate/bot controls                   | Configuration tests                        |
| False precision                          | API schema cannot return measurements on retake; readiness fails without model | Contract tests                             |

## Enforced production/research boundary

The production Python package has no training-framework, object-storage, database, temporary-file, or telemetry-export dependencies. Its application modules have no filesystem-write calls. The multipart parser's memory spool threshold is configured one byte above the total request-body ceiling; both declared-length and chunked requests are stopped before they can cross that ceiling. The container build copies only `pyproject.toml` and `app/`; neither `ml/` nor the repository root enters the image. Production modules are forbidden from importing the research package or common persistence/training clients. Browser source is forbidden from using persistent web storage, Cache Storage, storage management, or beacon export APIs. The model-tooling workflow is manual and has no artifact-download or cloud-auth step. `test_privacy_boundary.py` enforces these constraints in standard CI.

`verify_privacy_release_boundary.py` adds a fail-closed release audit. Runtime dependency sets, Terraform resource addresses/types, and referenced structured-log fields are explicitly reviewed; any new package, infrastructure instance, or payload field fails until the privacy allow-list is consciously updated. The audit also requires disabled Uvicorn access logs, native load-balancer metadata logging without optional fields, query-stripping HTTP redirects, one fixed query-free browser upload path, and a self-only browser script policy without CSP reporting. CI retains only the resulting counts and booleans in a 30-day `nailsize-privacy-release-boundary@1` artifact.

The Cloud Run benchmark job never receives a customer capture. It loads the model with a fixed synthetic tensor and emits one structured stdout object containing only deployment/model identifiers, tensor dimensions, iteration counts, aggregate latency, and pass/fail checks. The deployment workflow scopes retrieval to that execution and retains the independently verified aggregate report; neither the raw tensor nor model output is serialized.

Dynamic tests install a Python runtime audit hook around accepted measurement, malformed upload, timeout, and cancellation paths. They fail on filesystem opens with write flags or file/directory mutation events and require interrupted upload buffers to close. The Linux image smoke runs the production process with a read-only root filesystem, all Linux capabilities dropped, and `no-new-privileges`. MediaPipe's Matplotlib import needs a non-customer font/config cache, so `MPLCONFIGDIR` is confined to a 16 MiB, non-executable `/tmp` tmpfs. After a malformed upload, CI terminates the process and requires `docker diff` to be empty. These controls cover the source-managed process boundary, not out-of-band platform integrations.

The inbound training boundary is also fail closed: every manifest row must identify the approved research-study origin and active research consent, participant split leakage is rejected, and training requires exact approved checksums for aggregate-only provenance and public-holdout lock reports. The lock recomputes every split using a protected salt held outside Git but publishes only aggregate counts and an identifier-free commitment. The selected checkpoint and ONNX export preserve the provenance, manifest, and holdout-lock identities. The eleven-file release additionally requires aggregate segmentation evidence whose private observation identities reproduce the holdout commitment, but whose published report contains only model/dataset identities, counts, metrics, intervals, and named reviews. These controls establish source-managed chain of custody; they cannot prove that a human supplied truthful study metadata or that remote IAM is configured correctly.

Together these repository boundaries prevent the application from exporting uploads into the available training path and prevent the supported training/release workflow from accepting an unapproved manifest. Deployment review must still verify that the Cloud Run identity has no write access to research storage and that no platform integration captures request bodies.

## Remaining production reviews

- Inspect applied Cloud Run and load-balancer logging to confirm request/response bodies are absent and no out-of-band integration changed the source-managed policy.
- Verify Vercel analytics, browser error reporting, and session replay are disabled or payload-safe.
- Verify the deployed Vercel project has no dashboard-enabled analytics, speed-insight, session-replay, or error-reporting integration outside repository source.
- Run container and dependency scans for every release.
- Perform deletion/cancellation/process-termination tests against staging telemetry.
