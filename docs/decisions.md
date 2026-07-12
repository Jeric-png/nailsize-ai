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

## ADR-005 — Do not show a fake second inference delay

- Status: Accepted
- Decision: Each capture displays the Stitch quality-analysis state while its real API request runs. After the fourth accepted response, the processing screen reports the completed stages and lets the user review results; it does not replay a decorative progress delay.
- Reason: The API already performs quality, calibration, segmentation, measurement, and mapping synchronously for each capture. A later animated wait would misrepresent system activity and harm assistive-technology users.

## ADR-006 — Make recovery contextual and account-free

- Status: Accepted
- Decision: Network, file-type, payload-size, rate-limit, and service errors appear beside the affected capture. A missing browser-memory session has a dedicated privacy-safe reset screen.
- Reason: The Stitch recovery concepts are retained, but “sign in again” is inapplicable because the product has no accounts or persistence.

## ADR-007 — Preserve Stitch result hierarchy with measurement evidence

- Status: Accepted
- Decision: Mobile results use left/right hand tabs; desktop results use two five-nail panels beside actions. Projected millimetres, uncertainty, confidence, alternate sizes, and capture-level retakes remain visible even where the wireframe is more compact.
- Reason: The calibrated measurement evidence and honest correction controls are product safety requirements and take precedence over literal wireframe density.

## ADR-008 — Treat four-photo feasibility as a fail-closed launch gate

- Status: Accepted
- Decision: An underpowered or incompletely reviewed study remains insufficient evidence. A sufficiently powered four-photo study that misses any measurement, size, or required cohort target blocks launch and requires a separately designed and validated oblique-capture fallback.
- Reason: Study incompleteness and protocol failure require different actions, and tooling must not silently invent a new capture experience.

## ADR-009 — Keep emulation separate from client certification

- Status: Accepted
- Decision: Playwright engine and device-emulation runs remain required CI checks, but production client certification requires real branded browser versions, physical iOS/Android devices, and manual keyboard, VoiceOver, and TalkBack evidence.
- Reason: Engine emulation cannot prove camera behavior, operating-system integration, or assistive-technology usability on the required release matrix.
