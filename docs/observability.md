# Observability Contract

The inference service emits one JSON object per line through the `nailsize.inference` logger. Its dedicated handler does not add a Uvicorn prefix, so Cloud Run parses fields into `jsonPayload` and recognizes the automatic `severity` field. Fields are fail-closed through `safe_log`; photos, filenames, contours, widths, size recommendations, and result bodies are not accepted.

## Events and derived metrics

| Event | Safe dimensions | Metric use |
| --- | --- | --- |
| `runtime_initialized` | `ready`, `cold_start`, model/chart version, error code | cold starts and initialization failures |
| `request_completed` | server request ID, status, total latency, model/chart version | request count, error rate, and latency percentiles |
| `stage_completed` | server request ID, stage, duration, model/chart version | decode and quality-stage latency |
| `measurement_retake` | error code, image dimensions/bytes, total latency, versions | retake reason and malformed-input trends |
| `request_failed` | status and sanitized error code | unexpected service failures |

The service generates each request ID; it never copies an untrusted identifier from a header into telemetry. Uvicorn access logging is disabled in the production container.

## Provisioning

`infra/observability` provides validated Terraform for:

- 30-day retention on the project `_Default` log bucket;
- stage-latency, measurement-outcome, cold-start, and malformed-upload log metrics;
- request/error counts, p50/p95/p99 total and stage latency, retake reasons, cold starts, saturation, concurrency, CPU/memory utilization, startup latency, billable time, and model/chart-version dashboard panels;
- 5xx ratio, p95 latency, maximum-instance saturation, and malformed-upload alerts; and
- a project-scoped billing budget with explicitly supplied thresholds.

Alert thresholds, budget values, notification channels, and the project are required inputs with no production defaults. CI runs `terraform validate` and fail-closed variable tests without credentials. Provisioning still requires authorized staging/production credentials, an approved remote state backend, and post-apply evidence.

Cloud Run native metrics use the documented `run.googleapis.com/request_count`, `request_latencies`, `container/instance_count`, and `container/max_request_concurrencies` metric types. Log metrics are deliberately few and use bounded labels to control cardinality and cost.
