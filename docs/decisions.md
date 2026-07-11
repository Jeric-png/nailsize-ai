# Architecture and Product Decisions

## ADR-001 — Separate static web and inference deployments

- Status: Accepted
- Decision: Deploy the Vite frontend on Vercel and the CPU inference container on Cloud Run. The browser uploads each capture directly to the inference origin.
- Reason: Vercel is appropriate for the static experience, while the computer-vision runtime needs explicit CPU, memory, concurrency, timeout, and model lifecycle controls.
- Consequence: CORS is allow-listed and the frontend requires `VITE_INFERENCE_API_URL`.

## ADR-002 — Fail closed before calibrated inference is available

- Status: Accepted
- Decision: The API returns a typed retake response whenever reference calibration, segmentation, or confidence is unavailable. It cannot manufacture projected widths or sizes.
- Reason: A plausible number without calibrated evidence is more harmful than a clear retake.

## ADR-003 — No production persistence layer

- Status: Accepted
- Decision: The measurement path has no database, object store, queue, request-body tracing, or image cache.
- Reason: Images are required only for synchronous inference and must be discarded in every outcome.

## ADR-004 — Accuracy certification is an external release gate

- Status: Accepted
- Decision: Software tests can prove geometry and workflow behavior, but public accuracy claims require the participant-disjoint studies in `outputs/plan.md`.
- Reason: Synthetic fixtures cannot establish performance on real people, devices, nail shapes, or skin tones.
