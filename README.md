# NailSize Guide

NailSize Guide is a browser-only web application that turns one photo of one nail into a reviewable **projected planar width** and one conservative best-fit suggestion. The user selects the digit and explicitly asks the app to treat the round reference in the photo as exactly `23.00 mm`.

The automatic route is `/instant`. It is an experimental sizing aid, not a validated accuracy or fit guarantee. The manual `guided-sg50-coin-v1` workflow remains available as rollback.

## Single-nail beta

1. Choose the digit and upload one JPEG, PNG, or WebP photo containing one bare nail and one complete round reference.
2. Confirm the `23.00 mm` reference assumption.
3. The browser loads pinned same-origin ONNX/WASM assets, proposes the reference rim and nail boundary, and calculates projected width locally.
4. If other circles or clutter confuse the detector, tap the reference centre once; the app fits the rim automatically. It never asks for eight rim markers in this route.
5. Review the proposed nail width if requested and receive exactly one best-fit suggestion or an out-of-chart result.

The app does not identify the coin or verify its diameter. Using a different-size object while confirming `23.00 mm` scales the result incorrectly.

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

Selected photos are processed in browser memory and are not uploaded. HEIC is currently unsupported; convert it locally to JPEG, PNG, or WebP before selection.
