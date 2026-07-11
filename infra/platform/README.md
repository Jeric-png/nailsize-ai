# Platform infrastructure

This Terraform root provisions the image-dependent portion of one isolated staging or production inference environment: Cloud Run, a global external HTTPS load balancer, a managed certificate, and a Cloud Armor per-IP throttle.

Apply `infra/bootstrap` first, then push the validated container to its Artifact Registry repository and resolve the immutable repository digest. No platform input has a deployable default. Create a private `terraform.tfvars` only after that digest, model evidence, domain, load-tested instance cap, and staging-derived traffic threshold are approved. Keep rate limiting in preview initially:

```sh
terraform -chdir=infra/platform init -backend=false
terraform -chdir=infra/platform test
```

Use a remote state backend before any authorized plan or apply:

```sh
terraform -chdir=infra/platform init \
  -backend-config="bucket=<approved-versioned-state-bucket>" \
  -backend-config="prefix=nailsize/<environment>/platform"
terraform -chdir=infra/platform plan -out=<environment>.tfplan
terraform -chdir=infra/platform apply <environment>.tfplan
```

After apply, point the API domain's DNS A record to `api_ip_address`; the Google-managed certificate will not become active until DNS resolves to the load balancer. Confirm Cloud Armor preview logs contain the expected client distribution before setting `rate_limit_preview = false` in a reviewed follow-up plan.

The platform derives the runtime service-account email created by `infra/bootstrap`; the account receives no project-level roles. The model and hand-landmarker assets must remain bundled in the immutable container image. `allUsers` receives only `roles/run.invoker`; Cloud Run ingress plus `default_uri_disabled` prevents direct internet bypass of the Cloud Armor-protected load balancer.
