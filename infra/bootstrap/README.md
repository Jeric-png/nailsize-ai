# Environment bootstrap

This Terraform root creates the prerequisites that must exist before an immutable inference image can be built and deployed: required Google Cloud APIs, an environment-specific Artifact Registry repository, and a dedicated runtime service account with no project-level roles.

Apply it once per staging or production project using remote state and a reviewed plan. The configured GCS state bucket must already exist; pass a unique prefix for this root and environment. Then authenticate Docker to the `artifact_repository_host`, push the validated image, resolve its repository digest, and supply that digest-pinned URI to `infra/platform`.

```sh
terraform -chdir=infra/bootstrap init \
  -backend-config="bucket=<approved-versioned-state-bucket>" \
  -backend-config="prefix=nailsize/<environment>/bootstrap"
terraform -chdir=infra/bootstrap plan -out=<environment>.tfplan
terraform -chdir=infra/bootstrap apply <environment>.tfplan
```

Do not grant the runtime identity storage, database, training, or model-registry access. Runtime model assets are bundled into the immutable container image.
