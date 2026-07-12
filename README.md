# NailSize Guide

NailSize Guide is a browser-only web application for estimating the **projected planar width** of all ten nails. It does not use an AI model, nail dataset, image API, or backend inference service.

The product contract and release boundaries are defined in [`PRD.md`](PRD.md).

## How sizing works

1. Confirm a current Third Series Singapore 50-cent coin: Port of Singapore on one face and a large `50` with `CENTS` on the other. Older Singapore 50-cent coins have different dimensions and are not supported.
2. Complete four capture groups: left fingers, left thumb, right fingers, and right thumb.
3. Take two independent photos for each group, moving the hand and phone between photos—eight photos total. The browser rejects an exact reuse of the first normalized image, but this guard cannot prove that physical repositioning occurred.
4. Keep the coin flat beside the nails, photograph directly overhead, place eight markers clockwise around its complete rim, then mark both visible side edges of each nail.
5. The app converts the markers to prepared-image pixel coordinates and uses the coin’s official `23.00 mm` nominal diameter to establish a nearby scale. It rejects a coin under `120 prepared-image pixels`, diameter spread over `8%`, centre spread over `6%`, or nails farther than `4.5` coin diameters away. Separately, the marked coin must appear at least `120 CSS/screen pixels` wide in the annotation view so the controls remain usable; this display-size rule is an ergonomics guard, not accuracy validation.
6. The two readings for each nail must differ by no more than `0.6 mm`. Otherwise, the app requests a targeted retake instead of returning a recommendation.

The result shows the average projected width and selects a default press-on size conservatively from the wider repeat. The built-in `18–9 mm` chart is a starting point; nail artists should replace it with their actual tip supplier’s measured chart.

## Important limitation

The app measures a projected width using a local scale; it does not perform full perspective correction. Coin manufacturing tolerance, camera tilt, lens distortion, nail height, and marker placement remain error sources. It does not measure nail curvature, guarantee press-on fit, or replace a physical sizing kit. The `0.6 mm` rule checks capture repeatability, not real-world accuracy. Accuracy and tip-fit claims require a separate physical validation study.

The supported coin is documented by the [Singapore Currency Act legal specification](https://sso.agc.gov.sg/SL/CA1967-S347-2013?ProvIds=Sc-&ValidDate=20130611) and the [MAS Third Series release](https://www.nas.gov.sg/archivesonline/data/pdfdoc/20130228006/press_release.pdf).

## Privacy

Photos stay in the browser. They are not uploaded, stored, logged, or used for training. An in-memory SHA-256 fingerprint catches exact duplicate normalized repeats and is discarded with the photo. Local object URLs are released when a photo is replaced, a capture is accepted, the session is reset, or the page is closed. Supported inputs are JPEG, PNG, and WebP up to 12 MB. Before full decoding, the browser rejects a source over 20 megapixels or with either side over 8192 pixels; accepted sources are then oriented, downscaled to at most a 4096-pixel edge and 16 MP, and re-encoded locally.

Markers support pointer, touch, and keyboard adjustment. An arrow key moves a focused marker by one rendered CSS pixel; holding Shift moves it by eight rendered CSS pixels. These steps are based on the displayed annotation, not the prepared image's source pixels.

## Development

Node.js 22 or newer is required.

```bash
npm install
npm run dev
```

Verification commands:

```bash
npm run lint
npm run typecheck
npm test
npm run build
npm run verify:bundle
npm run test:e2e
npm run test:compat
```

`verify:bundle` rejects source maps, API endpoints, AI-provider references, and other forbidden network bindings in the production bundle.

## Deployment

The built Vite application is hosted directly on Vercel using [`vercel.json`](vercel.json). The runtime needs no OpenAI, Hugging Face, Google Cloud, model, dataset, or application environment key. The manual deployment workflow uses Vercel project/team identifiers, a protected production URL, and a `VERCEL_TOKEN` stored as a GitHub environment secret.

The former `services/inference/`, `ml/`, `packages/contracts/`, and `infra/` paths are retained as legacy research history. They are not part of the active web build or deployment path.
