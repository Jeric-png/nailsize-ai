# Privacy and Threat Model

## Data flow

1. The browser reads a user-selected photo into an in-memory `File` and object URL.
2. It posts one multipart capture directly to the inference API.
3. The API reads at most 12 MB, verifies and decodes at most 25 MP, normalizes orientation, and discards source metadata.
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
| Oversized/decompression upload           | Encoded and decoded limits before inference                                    | API adversarial tests                      |
| MIME spoofing or malformed decoder input | MIME, signature, format, animation, and decoder validation                     | API tests                                  |
| Payload leakage to logs/APM              | Allow-listed structured log fields; access logs disabled                       | Logging tests and production config review |
| Browser persistence                      | In-memory reducer, object URL revocation, no local/session storage             | Unit and E2E tests                         |
| Shared/proxy caching                     | `no-store`, `no-cache`, direct HTTPS API requests                              | Contract tests                             |
| Cross-origin abuse                       | Exact CORS allow-list and deployment-level rate/bot controls                   | Configuration tests                        |
| False precision                          | API schema cannot return measurements on retake; readiness fails without model | Contract tests                             |

## Remaining production reviews

- Verify Cloud Run request logging excludes bodies and query payloads.
- Verify Vercel analytics, browser error reporting, and session replay are disabled or payload-safe.
- Run container and dependency scans for every release.
- Perform deletion/cancellation/process-termination tests against staging telemetry.
