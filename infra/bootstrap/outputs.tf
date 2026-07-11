output "artifact_repository" {
  description = "Artifact Registry repository that accepts immutable inference images."
  value       = google_artifact_registry_repository.inference.name
}

output "artifact_repository_host" {
  description = "Registry host used when tagging the inference image."
  value       = "${var.region}-docker.pkg.dev"
}

output "runtime_service_account" {
  description = "Role-less service identity used by the inference container."
  value       = google_service_account.runtime.email
}
