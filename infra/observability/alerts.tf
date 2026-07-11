resource "google_monitoring_alert_policy" "error_rate" {
  project               = var.project_id
  display_name          = "NailSize ${var.environment}: 5xx error rate"
  combiner              = "OR"
  notification_channels = var.notification_channel_ids
  user_labels           = local.labels

  documentation {
    mime_type = "text/markdown"
    content   = "The Cloud Run 5xx request ratio exceeded the explicitly approved threshold. Check the active revision and sanitized `request_failed` events; never copy payload data into an incident."
  }

  conditions {
    display_name = "5xx ratio above ${var.error_rate_threshold}"

    condition_threshold {
      filter             = "metric.type=\"run.googleapis.com/request_count\" AND ${local.metric_filter} AND metric.labels.\"response_code_class\"=\"5xx\""
      denominator_filter = "metric.type=\"run.googleapis.com/request_count\" AND ${local.metric_filter}"
      comparison         = "COMPARISON_GT"
      threshold_value    = var.error_rate_threshold
      duration           = "300s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }

      denominator_aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }

      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }
}

resource "google_monitoring_alert_policy" "p95_latency" {
  project               = var.project_id
  display_name          = "NailSize ${var.environment}: p95 request latency"
  combiner              = "OR"
  notification_channels = var.notification_channel_ids
  user_labels           = local.labels

  documentation {
    mime_type = "text/markdown"
    content   = "Cloud Run p95 container request latency exceeded ${var.p95_latency_threshold_ms} ms for five minutes. Compare stage-latency distributions before changing capacity or model behavior."
  }

  conditions {
    display_name = "p95 above ${var.p95_latency_threshold_ms} ms"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_latencies\" AND ${local.metric_filter}"
      comparison      = "COMPARISON_GT"
      threshold_value = var.p95_latency_threshold_ms
      duration        = "300s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_PERCENTILE_95"
        cross_series_reducer = "REDUCE_MAX"
      }

      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }
}

resource "google_monitoring_alert_policy" "instance_saturation" {
  project               = var.project_id
  display_name          = "NailSize ${var.environment}: instance saturation"
  combiner              = "OR"
  notification_channels = var.notification_channel_ids
  user_labels           = local.labels

  documentation {
    mime_type = "text/markdown"
    content   = "Active Cloud Run instances reached the configured maximum (${var.max_instances}) for five minutes. Inspect pending requests and edge-generated 429 responses before raising the cost cap."
  }

  conditions {
    display_name = "Active instances reached maximum"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/container/instance_count\" AND ${local.metric_filter} AND metric.labels.\"state\"=\"active\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.max_instances - 0.5
      duration        = "300s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_MAX"
        cross_series_reducer = "REDUCE_SUM"
      }

      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }
}

resource "google_monitoring_alert_policy" "malformed_upload_spike" {
  project               = var.project_id
  display_name          = "NailSize ${var.environment}: malformed upload spike"
  combiner              = "OR"
  notification_channels = var.notification_channel_ids
  user_labels           = local.labels

  documentation {
    mime_type = "text/markdown"
    content   = "Sanitized 413, 415, or 422 request outcomes exceeded ${var.malformed_uploads_per_minute_threshold} per minute. Investigate abuse and client regressions using counts only; do not retain uploaded content."
  }

  conditions {
    display_name = "Malformed uploads above approved rate"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.malformed_uploads.name}\" AND ${local.metric_filter}"
      comparison      = "COMPARISON_GT"
      threshold_value = var.malformed_uploads_per_minute_threshold / 60
      duration        = "300s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }

      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }
}
