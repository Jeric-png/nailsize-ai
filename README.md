# NailSize AI

A web application that estimates a customer's nail dimensions from a calibrated photograph so nail artists can produce correctly sized press-on nails.

## Project status

Implementation is underway. The current foundation includes a Vercel-ready React application, a fail-closed FastAPI image endpoint, ISO ID-1 reference detection, deterministic size mapping, and automated frontend/backend/browser checks. Real-world accuracy is not yet certified and remains gated on the participant studies in [`outputs/plan.md`](outputs/plan.md).

## Intended deployment

- Static web application hosted on Vercel
- CPU inference service hosted on Google Cloud Run
- Browser upload with server-side, ephemeral image processing
- No permanent storage of customer nail photographs
- Computer-vision sizing validated against a physical reference marker

## Development

```bash
npm install
python3.12 -m venv .venv
.venv/bin/pip install -e 'services/inference[dev]'
npm run dev
```

Run verification with `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, `npm run test:e2e`, and `.venv/bin/pytest services/inference/tests`.

Do not commit secrets. Use `.env.local` for the frontend, `.env` for the local API, Vercel environment variables for the deployed web application, and Google Cloud secret/configuration management for Cloud Run.
