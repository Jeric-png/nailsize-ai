# Production Release Readiness

`release_readiness.py` is the final fail-closed aggregation gate. It does not replace model, deployment, privacy, browser, security, or human review. It proves that their approved reports describe one production release and that none of the required external evidence is missing.

## Evidence directory

Create a private working directory containing exactly these aggregate-only files:

- `model-release-manifest.json`
- `github-environment-audit.json`
- `staging-promotion.json`
- `deployment-manifest.json`
- `onnx-runtime-benchmark.json`
- `runtime-model-verification.json`
- `image-promotion.json`
- `vercel-deployment.json`
- `deployment-smoke.json`
- `client-certification.json`
- `privacy-release-boundary.json`
- `release-attestations.json`

The first eleven files are outputs of the existing release tools and deployment workflows. Download the exact production artifacts; do not rewrite them. A matching schema-version label alone is insufficient: the verifier requires every retained top-level field and the exact nested contracts for protected environments, Cloud Run benchmark metrics/checks, live smoke results, branded-browser records, and accessibility evidence. Missing or extra fields therefore cannot smuggle private payloads or impersonate a complete upstream report. `release-attestations.json` uses schema `nailsize-release-readiness-attestations@1`. It contains only the repository, immutable release version and commit, boolean/count results, and bounded evidence references—never reviewer names, email addresses, credentials, customer data, free-form notes, or scan payloads.

The attestation has three exact objects:

- `production_controls`: references for the production revision, infrastructure/environment isolation, IAM, logging, Vercel integrations, termination audit, observability, notification testing, and budget review; 30-day retention; and explicit pass booleans for each deployed control.
- `security_and_defects`: named review, deployed-image scan, repository security/control, and product-triage references, with critical/high vulnerability and severity-1/2 defect counts.
- `signoffs`: product, nail-tech, privacy/security, and engineering sign-off references.

Blank references are permitted only to generate an honest `insufficient_evidence` result. Invalid or extra fields fail parsing.

## Run the gate

```sh
python services/inference/scripts/release_readiness.py \
  /approved-evidence/release-candidate \
  --output /approved-evidence/release-readiness.json
```

The verifier cross-checks the repository, release commit, model tag/version/checksum, staging-to-production image digest, production frontend/API hosts, runtime identity, benchmark, smoke contract, and client certification. It records a SHA-256 for every input artifact so the retained report can bind the exact evidence bytes. It returns:

- `release_ready` only when every schema, identity, deployed control, scan/triage count, reference, and sign-off passes;
- `insufficient_evidence` when an artifact schema or accountable reference is missing; or
- `release_blocked` when complete evidence contains a failed control, identity mismatch, vulnerability, or priority defect.

Only `release_ready` exits zero and sets `public_launch_may_continue: true`. Link the generated report and every referenced immutable artifact in `docs/goal-evidence.md` before closing the goal.
