# Deployment

## Environment model

| Environment | Frontend                       | Inference                              | Purpose                                        |
| ----------- | ------------------------------ | -------------------------------------- | ---------------------------------------------- |
| Development | Vite on `localhost:5173`       | Uvicorn on `localhost:8000`            | Local implementation and tests                 |
| Staging     | Vercel preview/staging project | Dedicated Cloud Run staging service    | Integration, privacy, load, and device QA      |
| Production  | Vercel production deployment   | Dedicated Cloud Run production service | Public traffic after every release gate passes |

Never point a preview frontend at the production inference service. Configure a distinct `VITE_INFERENCE_API_URL` and exact `ALLOWED_ORIGINS` value for each environment.

## Vercel frontend

The repository root contains `vercel.json`. Connect `Jeric-png/nailsize-ai`, keep the project root at the repository root, and configure:

- Build command: `npm run build`
- Output directory: `apps/web/dist`
- Node.js: 22
- `VITE_INFERENCE_API_URL`: the matching HTTPS Cloud Run origin

Pull requests should receive preview deployments. Promote to production only after staging smoke, accessibility, privacy, and cross-browser checks pass.

## Cloud Run inference

Build `services/inference/Dockerfile` only after a verified ONNX model is available and its checksum is locked. Required runtime settings:

- 2 vCPU and 4 GiB memory
- one Uvicorn worker and request concurrency `1`
- minimum instances `1`
- application/request timeout of 15 seconds
- exact frontend CORS origin
- request-body and response-body logging disabled
- maximum instances and billing alerts set from the validated traffic model

## Rollback

- Frontend: promote the last known-good immutable Vercel deployment.
- API: route traffic to the previous Cloud Run revision.
- Model: deploy the previous container revision; models are immutable within an image.
- Size chart: revert the versioned code change and redeploy; never modify an existing chart version in place.
