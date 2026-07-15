# Image Decoder Provenance

The client pins `heic-to` `1.5.2` as a browser-only HEIC/HEIF fallback. Source:
[`hoppergee/heic-to` v1.5.2](https://github.com/hoppergee/heic-to/tree/v1.5.2),
licensed [LGPL-3.0](https://github.com/hoppergee/heic-to/blob/v1.5.2/LICENSE)
and built on libheif. The exact package tarball and integrity digest are
recorded in `package-lock.json`.

The app first asks the browser to decode HEIC/HEIF. Only when that fails does a
dynamic import load `heic-to/csp` from the same Vercel artifact. Conversion runs
locally, produces an in-memory bitmap, and makes no network request containing
the photo. JPEG, PNG, WebP, AVIF, GIF, and BMP use browser-native decoding and
do not load the fallback chunk.

Release review must preserve this notice and the upstream license, verify the
chunk remains lazy and same-origin, and test CSP, worker cleanup, peak memory,
and malformed-input failure on current mobile browsers. The decoder's singleton
worker has no public termination API, so low-memory and repeated-HEIC testing
remain explicit release checks rather than assumed guarantees.
