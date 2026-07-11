output "dashboard_id" {
  description = "Cloud Monitoring dashboard resource ID."
  value       = google_monitoring_dashboard.service.id
}

output "alert_policy_ids" {
  description = "Alert policies created for the inference service."
  value = {
    error_rate             = google_monitoring_alert_policy.error_rate.id
    p95_latency            = google_monitoring_alert_policy.p95_latency.id
    instance_saturation    = google_monitoring_alert_policy.instance_saturation.id
    malformed_upload_spike = google_monitoring_alert_policy.malformed_upload_spike.id
  }
}
