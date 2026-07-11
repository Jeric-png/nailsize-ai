output "api_ip_address" {
  description = "Global address to assign to the API domain's DNS A record."
  value       = google_compute_global_address.api.address
}

output "api_url" {
  description = "Canonical public inference origin."
  value       = "https://${var.api_domain}"
}

output "artifact_repository" {
  description = "Artifact Registry repository that accepts immutable inference images."
  value       = google_artifact_registry_repository.inference.name
}

output "cloud_run_service" {
  description = "Cloud Run service name behind the load balancer."
  value       = google_cloud_run_v2_service.inference.name
}

output "runtime_service_account" {
  description = "Role-less service identity used by the inference container."
  value       = google_service_account.runtime.email
}

output "cloud_armor_policy" {
  description = "Cloud Armor policy attached to the load balancer backend."
  value       = google_compute_security_policy.edge.name
}
