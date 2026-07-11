data "google_project" "current" {
  project_id = var.project_id
}

locals {
  service_filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.service_name}\""
  metric_filter  = "resource.type=\"cloud_run_revision\" AND resource.labels.\"service_name\"=\"${var.service_name}\""
  labels = {
    environment = var.environment
    managed_by  = "terraform"
    service     = var.service_name
  }
}

resource "google_logging_project_bucket_config" "default" {
  project        = var.project_id
  location       = "global"
  bucket_id      = "_Default"
  retention_days = 30
  description    = "Sanitized NailSize operational logs; customer photos and measurements are prohibited."
}

resource "google_logging_metric" "stage_latency" {
  project = var.project_id
  name    = "nailsize_stage_latency_ms"
  filter  = "${local.service_filter} AND jsonPayload.event=\"stage_completed\""

  metric_descriptor {
    display_name = "NailSize stage latency"
    metric_kind  = "DELTA"
    value_type   = "DISTRIBUTION"
    unit         = "ms"

    labels {
      key         = "stage"
      value_type  = "STRING"
      description = "Bounded inference stage name."
    }
  }

  value_extractor = "EXTRACT(jsonPayload.duration_ms)"
  label_extractors = {
    stage = "EXTRACT(jsonPayload.stage)"
  }

  bucket_options {
    explicit_buckets {
      bounds = [25, 50, 100, 250, 500, 1000, 2000, 5000, 10000, 15000]
    }
  }
}

resource "google_logging_metric" "measurement_events" {
  project = var.project_id
  name    = "nailsize_measurement_events"
  filter  = "${local.service_filter} AND (jsonPayload.event=\"measurement_completed\" OR jsonPayload.event=\"measurement_retake\")"

  metric_descriptor {
    display_name = "NailSize measurement events"
    metric_kind  = "DELTA"
    value_type   = "INT64"

    labels {
      key         = "event"
      value_type  = "STRING"
      description = "Completed or retake outcome."
    }
    labels {
      key         = "error_code"
      value_type  = "STRING"
      description = "Bounded retake reason; empty for accepted measurements."
    }
    labels {
      key         = "model_version"
      value_type  = "STRING"
      description = "Immutable model version."
    }
    labels {
      key         = "chart_version"
      value_type  = "STRING"
      description = "Immutable sizing-chart version."
    }
  }

  label_extractors = {
    event         = "EXTRACT(jsonPayload.event)"
    error_code    = "EXTRACT(jsonPayload.error_code)"
    model_version = "EXTRACT(jsonPayload.model_version)"
    chart_version = "EXTRACT(jsonPayload.chart_version)"
  }
}

resource "google_logging_metric" "cold_starts" {
  project = var.project_id
  name    = "nailsize_cold_starts"
  filter  = "${local.service_filter} AND jsonPayload.event=\"runtime_initialized\" AND jsonPayload.cold_start=true"

  metric_descriptor {
    display_name = "NailSize cold starts"
    metric_kind  = "DELTA"
    value_type   = "INT64"
  }
}

resource "google_logging_metric" "malformed_uploads" {
  project = var.project_id
  name    = "nailsize_malformed_uploads"
  filter  = "${local.service_filter} AND jsonPayload.event=\"request_completed\" AND (jsonPayload.status_code=413 OR jsonPayload.status_code=415 OR jsonPayload.status_code=422)"

  metric_descriptor {
    display_name = "NailSize malformed uploads"
    metric_kind  = "DELTA"
    value_type   = "INT64"
  }
}
