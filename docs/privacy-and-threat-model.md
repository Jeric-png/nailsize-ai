# Privacy and Threat Model

## Client data flow

The automatic single-nail beta is the primary `/instant` flow.

1. The browser accepts one JPEG/JFIF, PNG, WebP, HEIC/HEIF, AVIF, GIF, or BMP file no larger than 12 MB. Detection uses file signatures and bounded header parsing rather than trusting MIME or extension metadata.
2. Header checks reject a source over 20 MP or 8192 pixels on either edge before full decode. Accepted images are oriented, downscaled to at most a 4096-pixel edge and 16 MP, and re-encoded locally. HEIC/HEIF uses the browser decoder first and lazily loads a same-origin decoder fallback only when needed.
3. The client creates in-memory object URLs for review. Starting analysis fetches only pinned, same-origin application, ONNX, and WASM assets with `GET` requests.
4. Coin-rim detection, nail-mask inference, ellipse calibration, projected-width calculation, uncertainty handling, and chart mapping execute in browser memory. Photo bytes are inputs to local browser APIs and are never request bodies.
5. A usable nail and coin detection shows one size without calibration questions or editable markers. An unusable photo returns to upload with a single retake message. Results remain in React state until reset, reload, close, or unmount.
6. Copy exports a text summary after an explicit user action. The destination clipboard or share target is outside the application's control.

The guided fallback remains separate. It uses manual coin/nail markers and an in-memory SHA-256 fingerprint to reject exact reuse of a verification image. Neither flow uses an API route, server inference, database, object storage, analytics SDK, training export, or service-side image parser.

## Protected data

- Selected photos, filenames, source metadata, and incidental background content
- Image fingerprints used by the guided fallback
- Coin ellipse or rim coordinates, nail masks, sidewall coordinates, and correction provenance
- Projected widths, uncertainty, repeat differences, and preliminary size suggestions
- Text result summaries

The client must not persist these values in local storage, session storage, IndexedDB, Cache Storage, cookies, a service worker, logs, or telemetry. Normal HTTP caching may retain public application/model/WASM assets, never selected photos.

## Principal threats and controls

| Threat                                            | Control                                                                                                                                                                                                          | Required verification                                                        |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| A regression uploads a photo                      | Static architecture, no API dependency, and a same-origin-only connection policy; photo bytes must never enter `fetch`, forms, beacons, or telemetry                                                             | Unit, bundle, request-observing E2E, and deployed smoke checks               |
| Browser memory retains photos                     | Revoke object URLs and release decoded pixels, canvases, tensors, and results on replacement, failure, reset, unmount, and completion                                                                            | Lifecycle tests, memory-oriented review, and real-device reset/reload checks |
| A model/runtime asset is substituted              | Versioned same-origin paths, exact SHA-256 pins, fixed tensor contract, release manifest, and byte-identical deployment audit                                                                                    | Manifest/runtime tests, `verify:bundle`, and deployment verifier             |
| Third-party code observes the page                | No analytics, replay, error-reporting SDK, remote model provider, or injected integration; scripts are same-origin                                                                                               | Bundle/deployment checks and Vercel dashboard review                         |
| Malformed or oversized input stresses the browser | Content-signature allow-list, bounded JPEG/PNG/WebP/GIF/BMP/ISO-BMFF dimension preflight, animation rejection, bounded normalization, and fail-closed decode                                                     | Image-preparation unit and cross-browser fixture tests                       |
| Wrong reference creates the wrong scale           | The user must explicitly confirm the app should assume the visible round reference is exactly `23.00 mm`; calibration rejects weak/cropped/steep ellipse fits                                                    | Unit, content, and manual review                                             |
| Tilt or a distant reference misleads calibration  | Automatic ellipse guards require a complete rim, at least `120 px` minor diameter, axis ratio `0.72–1.02`, rim coverage at least `0.75`, residual at most `0.08`, and nail proximity within `4.5` coin diameters | Geometry tests and representative real-photo validation                      |
| A weak mask becomes a recommendation              | Minimum usability checks, a visible read-only overlay, and a retake for unusable geometry; the customer-facing result remains explicitly best-effort                                                             | Model/postprocess tests, component/E2E result flow, and physical validation  |
| Results imply false precision or fit              | Plain “estimated visible width” wording, displayed variation, uncertainty-aware chart mapping, curvature/no-fit disclaimer, and sizing-kit fallback                                                              | Content review and physical validation before accuracy claims                |
| Legacy backend is restored                        | Bundle rejects `/v1/measure`, localhost API, `VITE_INFERENCE_API_URL`, OpenAI, and Hugging Face inference endpoints                                                                                              | `npm run verify:bundle` and deployed smoke                                   |

## Boundary limitations

`connect-src 'self'` permits the same-origin model/WASM fetches required by the beta. It would also permit a future same-origin API, so CSP is defense in depth rather than proof of zero upload. `script-src 'self' 'wasm-unsafe-eval'` and `worker-src 'self' blob:` support the pinned runtimes, including the lazy HEIC/HEIF fallback. Code review, request-observing tests, static deployment inspection, and Vercel integration review remain necessary.

Browser re-encoding normally omits source metadata, but this is not a certified EXIF-scrubbing guarantee. Repository controls also cannot prevent a browser extension, compromised device, screenshot, operating-system share target, or shoulder surfing from exposing visible content.

## Release privacy and distribution review

For every public automatic-beta deployment:

- prove all runtime requests are same-origin `GET` and no request body contains photo or result data;
- verify the exact model/WASM hashes and complete release-artifact digest;
- confirm there are no functions, API routes, analytics, replay, error reporting, injected integrations, or persistent storage;
- exercise replacement, correction, failure, reset, reload, and close on current iOS Safari and Android Chrome;
- confirm copied/shared output is text only; and
- retain attribution and the documented model CC BY 4.0/embedded AGPL-3.0 and image-decoder LGPL-3.0 notices, with long-term interpretation tracked as an open project risk.

Passing privacy checks does not establish model quality, physical measurement accuracy, completion time, or tip fit. Those are independent release gates. The legacy Python inference and ML trees remain outside the active boundary.
