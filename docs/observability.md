# Observability Contract

The inference service emits structured JSON through the `nailsize.inference` logger. Fields are fail-closed through `safe_log`; photos, filenames, contours, widths, size recommendations, and result bodies are not accepted.

## Events and derived metrics

| Event | Safe dimensions | Metric use |
| --- | --- | --- |
| `runtime_initialized` | `ready`, `cold_start`, model/chart version, error code | cold starts and initialization failures |
| `request_completed` | server request ID, status, total latency, model/chart version | request count, error rate, and latency percentiles |
| `stage_completed` | server request ID, stage, duration, model/chart version | decode and quality-stage latency |
| `measurement_retake` | error code, image dimensions/bytes, total latency, versions | retake reason and malformed-input trends |
| `request_failed` | status and sanitized error code | unexpected service failures |

The service generates each request ID; it never copies an untrusted identifier from a header into telemetry. Uvicorn access logging is disabled in the production container.

## Deployment work

Create log-based counters and distributions from these events, then combine them with Cloud Run native instance count, concurrency, CPU, memory, startup, and billable-time metrics. Dashboards must show p50/p95/p99 total and stage latency, 4xx/5xx rate, retake reasons, cold starts, saturation, model/chart versions, and malformed-upload spikes. Alerts, 30-day retention, and dashboard links require the staging/production projects and remain release gates.
