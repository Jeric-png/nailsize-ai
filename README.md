# NailSize Guide

NailSize Guide is a browser-only web application that turns one photo of one nail beside a Singapore 50-cent coin into one best-fit press-on size suggestion.

The automatic route is `/instant`. It is an experimental sizing aid, not a validated accuracy or fit guarantee. The manual `guided-sg50-coin-v1` workflow remains available as rollback.

## Single-nail beta

1. Upload one JPEG/JFIF, PNG, WebP, HEIC/HEIF, AVIF, GIF, or BMP photo containing one bare nail and one complete Singapore 50-cent coin.
2. Select **Get my nail size**.
3. The browser loads pinned same-origin ONNX/WASM assets, detects the coin and nail boundary, and calculates a projected width locally.
4. Receive one best-fit size. The nearest size `0–9` is used even when the photo estimate falls beyond the provisional chart.
5. If either object cannot be found, the only recovery is a plain request for another photo; the customer is never asked to place calibration markers.

The app treats the automatically detected round object as a 23 mm Singapore 50-cent coin; it does not verify the denomination. Using a different-size object scales the result incorrectly.

## Accuracy and model status

The beta estimates projected width rather than curved nail-surface length. Perspective, lens distortion, nail height, reference placement, segmentation, and the provisional chart can affect the output. It does not guarantee fit or replace a physical sizing kit.

The pinned `mnemic/nails_seg_yolov8` artifact and exact hashes are documented in [`docs/automatic-model-provenance.md`](docs/automatic-model-provenance.md). The upstream card states CC BY 4.0 while the exported graph contains AGPL-3.0 metadata; the repository preserves attribution, and long-term distribution interpretation still requires confirmation.

## Development

```bash
npm install
npm run dev
npm run lint
npm run typecheck
npm test
npm run build
npm run verify:bundle
npm run test:e2e
npm run test:compat
```

The product and design contracts are in [`PRD.md`](PRD.md) and [`DESIGN.md`](DESIGN.md).

## Deployment

Vercel serves a static Vite artifact. There is no API route, inference server, database, OpenAI request, Hugging Face runtime dependency, or application secret. Deployment is performed by the protected GitHub Actions workflow after local and CI release checks pass.

Selected photos are detected by file content, normalized in browser memory, and never uploaded. HEIC/HEIF uses native browser decoding when available and otherwise loads the pinned, same-origin `heic-to` fallback only for that photo type.
