# Privacy and Threat Model

## Active data flow

1. The browser accepts a JPEG, PNG, or WebP file no larger than 12 MB.
2. Before full decoding, the client reads the supported image header and rejects a source over 20 MP or with either side over 8192 pixels. Browser APIs then orient and downscale accepted images to at most 4096 pixels on an edge and 16 MP, and re-encode them as JPEG. A header, decode, or re-encode failure is rejected; the app does not retain the original file as a fallback preview.
3. The client computes an in-memory SHA-256 fingerprint of the normalized image. An exact duplicate of the first image cannot be used as the verification photo.
4. The client creates an in-memory object URL and displays it behind local marker controls.
5. Third Series coin calibration, projected-width calculation, two-photo comparison, and chart mapping run synchronously in client JavaScript.
6. Accepting or clearing a capture revokes its object URLs and discards its fingerprint. Results remain only in the in-memory React reducer until reset, reload, close, or unmount.
7. Copy/share exports a text summary only after an explicit user action. The browser or operating-system share target is then outside this application's control.

There is no `fetch` or form upload in the measurement flow, no active API route, and no production database, object storage, queue, model provider, analytics SDK, training export, or service-side image parser. Normal static page and asset requests still reach Vercel; selected photos are never request bodies.

## Protected data

- Selected photos, filenames, and embedded metadata
- Normalized-image fingerprints, Third Series coin confirmation, coin-rim coordinates, and nail-edge coordinates
- Individual projected widths, repeat differences, and size suggestions
- Text result summaries and any incidental background content visible in a photo

The client does not persist these values in local storage, session storage, IndexedDB, Cache Storage, cookies, or a service worker.

## Principal threats and controls

| Threat                                                  | Current control                                                                                                                                                             | Verification                                                                                               |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Regression uploads a photo                              | Static-only architecture; same-origin-only CSP; no API dependency; E2E requires all observed requests to be same-origin `GET`                                               | Unit, bundle, E2E, and deployed smoke checks                                                               |
| Browser persistence leaves photos behind                | In-memory reducer; object URL revocation on replacement, acceptance, restart, reset, coin-confirmation withdrawal, and unmount; no persistent storage APIs                  | Session tests cover acceptance, reopen, coin-confirmation withdrawal, and reset; E2E covers reset/recovery |
| Third-party telemetry observes the page                 | No analytics/error-reporting SDK; self-only script policy; integrations must remain disabled in Vercel                                                                      | Bundle/deployment checks and dashboard review                                                              |
| Malformed or oversized local image stresses the browser | JPEG/PNG/WebP allow-list; 12 MB source limit; header preflight rejects over 20 MP or either side over 8192 px before full decode; fail-closed 4096-edge/16 MP normalization | Image-preparation unit tests and browser tests                                                             |
| One image is reused as both independent observations    | In-memory SHA-256 comparison of normalized image bytes rejects an exact duplicate; UI still instructs physical repositioning                                                | Unit and E2E duplicate-image checks                                                                        |
| Wrong 50-cent coin produces the wrong scale             | Mandatory Third Series design confirmation; guidance rejects older, commemorative, damaged, and foreign coins                                                               | Session/component tests and manual certification                                                           |
| Tilt or distant reference creates misleading scale      | Eight rim markers; `120` prepared-image-pixel geometry minimum; `8%` diameter-spread, `6%` centre-spread, and `4.5`-diameter proximity guards                               | Geometry unit tests and full-flow E2E                                                                      |
| Coin controls are too small to mark reliably            | Separate `120 CSS/screen px` rendered-annotation minimum; this is an ergonomics guard and is not treated as accuracy evidence                                               | Component and high-resolution browser tests                                                                |
| Shared-device or shoulder-surfing exposure              | No server history; explicit erase/reset; session disappears on reload/close                                                                                                 | Content and manual review                                                                                  |
| Text is shared unintentionally                          | Copy/share requires a user gesture and includes no photo                                                                                                                    | E2E copy test and manual platform review                                                                   |
| False precision or poor fit                             | Independent repeat gate; projected-width label; no-homography warning; conservative chart mapping; curvature and no-fit disclaimers                                         | Geometry tests, content review, physical validation before accuracy claims                                 |
| Legacy backend is accidentally restored                 | Bundle rejects `/v1/measure`, localhost API, `VITE_INFERENCE_API_URL`, OpenAI, and Hugging Face references                                                                  | `npm run verify:bundle` and deployed smoke                                                                 |

## Boundary limitations

`connect-src 'none'` blocks `fetch`, XHR, WebSocket, EventSource, and beacon connections, including to a future same-origin endpoint. Code review, static deployment configuration, request-observing E2E tests, and Vercel project review remain required because policy can be changed by a later release. Repository controls also cannot prove that a browser extension, compromised device, operating-system share target, or dashboard-added Vercel integration does not capture screen content.

Browser re-encoding normally removes source metadata, but this is an implementation side effect rather than a certified EXIF-scrubbing guarantee. The client reads supported-format dimensions from the source header before full decoding and rejects sources beyond the documented limits. Malformed files within those limits can still exercise the browser decoder, so decode failures remain a local availability test case even though failed normalization is rejected and nothing is uploaded.

## Release privacy review

Before each public release:

- inspect the built bundle and deployed network log for non-GET or cross-origin requests;
- confirm Vercel has no analytics, replay, error-reporting, deploy-hook, or third-party integration that injects client code;
- verify no serverless functions or API routes exist in the project;
- exercise replacement, accepted capture, restart, results reset, reload, and close paths on a real mobile browser; and
- confirm copied/shared output contains text only.

The legacy Python inference and ML research trees are outside the active production boundary. Their historical controls do not establish, and are not required for, the privacy of the browser-only release.
