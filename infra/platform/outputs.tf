output "api_ip_address" {
  description = "Global address to assign to the API domain's DNS A record."
  value       = google_compute_global_address.api.address
}

output "api_url" {
  description = "Canonical public inference origin."
  value       = "https://${var.api_domain}"
}

output "cloud_run_service" {
  description = "Cloud Run service name behind the load balancer."
  value       = google_cloud_run_v2_service.inference.name
}

output "cloud_run_benchmark_job" {
  description = "Cloud Run Job that benchmarks the immutable inference image on the target CPU configuration."
  value       = google_cloud_run_v2_job.onnx_benchmark.name
}

output "runtime_service_account" {
  description = "Role-less service identity used by the inference container."
  value       = local.runtime_service_account_email
}

output "cloud_armor_policy" {
  description = "Cloud Armor policy attached to the load balancer backend."
  value       = google_compute_security_policy.edge.name
}
