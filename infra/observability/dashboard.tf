locals {
  dashboard_widgets = [
    {
      text = {
        format = "MARKDOWN"
        content = join("\n", [
          "# NailSize ${var.environment}",
          "Privacy-safe operational metadata only. Customer photos, contours, widths, sizes, and result bodies are prohibited from logs.",
          "Configured gates: 5xx ratio `${var.error_rate_threshold}`, p95 `${var.p95_latency_threshold_ms} ms`, maximum instances `${var.max_instances}`, malformed uploads `${var.malformed_uploads_per_minute_threshold}/minute`."
        ])
      }
    },
    {
      title = "Requests by response class"
      xyChart = {
        dataSets = [{
          plotType = "STACKED_BAR"
          timeSeriesQuery = {
            timeSeriesFilter = {
              filter = "metric.type=\"run.googleapis.com/request_count\" AND ${local.metric_filter}"
              aggregation = {
                alignmentPeriod    = "60s"
                perSeriesAligner   = "ALIGN_RATE"
                crossSeriesReducer = "REDUCE_SUM"
                groupByFields      = ["metric.label.response_code_class"]
              }
            }
          }
        }]
        yAxis = { label = "requests/second", scale = "LINEAR" }
      }
    },
    {
      title = "Request latency p50 / p95 / p99"
      xyChart = {
        dataSets = [
          for percentile in [50, 95, 99] : {
            legendTemplate = "p${percentile}"
            plotType       = "LINE"
            timeSeriesQuery = {
              timeSeriesFilter = {
                filter = "metric.type=\"run.googleapis.com/request_latencies\" AND ${local.metric_filter}"
                aggregation = {
                  alignmentPeriod    = "60s"
                  perSeriesAligner   = "ALIGN_PERCENTILE_${percentile}"
                  crossSeriesReducer = "REDUCE_MAX"
                }
              }
            }
          }
        ]
        thresholds = [{ value = var.p95_latency_threshold_ms, color = "RED", direction = "ABOVE" }]
        yAxis      = { label = "milliseconds", scale = "LINEAR" }
      }
    },
    {
      title = "Inference stage latency p50 / p95 / p99"
      xyChart = {
        dataSets = [
          for percentile in [50, 95, 99] : {
            legendTemplate = "$${metric.label.stage} p${percentile}"
            plotType       = "LINE"
            timeSeriesQuery = {
              timeSeriesFilter = {
                filter = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.stage_latency.name}\" AND ${local.metric_filter}"
                aggregation = {
                  alignmentPeriod    = "60s"
                  perSeriesAligner   = "ALIGN_PERCENTILE_${percentile}"
                  crossSeriesReducer = "REDUCE_MAX"
                  groupByFields      = ["metric.label.stage"]
                }
              }
            }
          }
        ]
        yAxis = { label = "milliseconds", scale = "LINEAR" }
      }
    },
    {
      title = "Measurement outcomes and retake reasons"
      xyChart = {
        dataSets = [{
          legendTemplate = "$${metric.label.event} $${metric.label.error_code}"
          plotType       = "STACKED_BAR"
          timeSeriesQuery = {
            timeSeriesFilter = {
              filter = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.measurement_events.name}\" AND ${local.metric_filter}"
              aggregation = {
                alignmentPeriod    = "60s"
                perSeriesAligner   = "ALIGN_RATE"
                crossSeriesReducer = "REDUCE_SUM"
                groupByFields      = ["metric.label.event", "metric.label.error_code"]
              }
            }
          }
        }]
        yAxis = { label = "events/second", scale = "LINEAR" }
      }
    },
    {
      title = "Active instances"
      xyChart = {
        dataSets = [{
          plotType = "LINE"
          timeSeriesQuery = {
            timeSeriesFilter = {
              filter = "metric.type=\"run.googleapis.com/container/instance_count\" AND ${local.metric_filter} AND metric.labels.\"state\"=\"active\""
              aggregation = {
                alignmentPeriod    = "60s"
                perSeriesAligner   = "ALIGN_MAX"
                crossSeriesReducer = "REDUCE_SUM"
              }
            }
          }
        }]
        thresholds = [{ value = var.max_instances, color = "RED", direction = "ABOVE" }]
        yAxis      = { label = "instances", scale = "LINEAR" }
      }
    },
    {
      title = "Maximum concurrent requests per instance"
      xyChart = {
        dataSets = [{
          plotType = "LINE"
          timeSeriesQuery = {
            timeSeriesFilter = {
              filter = "metric.type=\"run.googleapis.com/container/max_request_concurrencies\" AND ${local.metric_filter} AND metric.labels.\"state\"=\"active\""
              aggregation = {
                alignmentPeriod    = "60s"
                perSeriesAligner   = "ALIGN_PERCENTILE_99"
                crossSeriesReducer = "REDUCE_MAX"
              }
            }
          }
        }]
        thresholds = [{ value = 1, color = "YELLOW", direction = "ABOVE" }]
        yAxis      = { label = "requests", scale = "LINEAR" }
      }
    },
    {
      title = "Cold starts and malformed uploads"
      xyChart = {
        dataSets = [
          for metric_name in [google_logging_metric.cold_starts.name, google_logging_metric.malformed_uploads.name] : {
            legendTemplate = metric_name
            plotType       = "LINE"
            timeSeriesQuery = {
              timeSeriesFilter = {
                filter = "metric.type=\"logging.googleapis.com/user/${metric_name}\" AND ${local.metric_filter}"
                aggregation = {
                  alignmentPeriod    = "60s"
                  perSeriesAligner   = "ALIGN_RATE"
                  crossSeriesReducer = "REDUCE_SUM"
                }
              }
            }
          }
        ]
        yAxis = { label = "events/second", scale = "LINEAR" }
      }
    },
    {
      title = "Model and chart versions"
      xyChart = {
        dataSets = [{
          legendTemplate = "model=$${metric.label.model_version} chart=$${metric.label.chart_version}"
          plotType       = "STACKED_BAR"
          timeSeriesQuery = {
            timeSeriesFilter = {
              filter = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.measurement_events.name}\" AND ${local.metric_filter}"
              aggregation = {
                alignmentPeriod    = "300s"
                perSeriesAligner   = "ALIGN_RATE"
                crossSeriesReducer = "REDUCE_SUM"
                groupByFields      = ["metric.label.model_version", "metric.label.chart_version"]
              }
            }
          }
        }]
        yAxis = { label = "events/second", scale = "LINEAR" }
      }
    },
    {
      title = "CPU and memory utilization p95"
      xyChart = {
        dataSets = [
          for metric_name in ["cpu", "memory"] : {
            legendTemplate = "${metric_name} p95"
            plotType       = "LINE"
            timeSeriesQuery = {
              timeSeriesFilter = {
                filter = "metric.type=\"run.googleapis.com/container/${metric_name}/utilizations\" AND ${local.metric_filter}"
                aggregation = {
                  alignmentPeriod    = "60s"
                  perSeriesAligner   = "ALIGN_PERCENTILE_95"
                  crossSeriesReducer = "REDUCE_MAX"
                }
              }
            }
          }
        ]
        yAxis = { label = "utilization", scale = "LINEAR" }
      }
    },
    {
      title = "Container startup latency p95"
      xyChart = {
        dataSets = [{
          plotType = "LINE"
          timeSeriesQuery = {
            timeSeriesFilter = {
              filter = "metric.type=\"run.googleapis.com/container/startup_latencies\" AND ${local.metric_filter}"
              aggregation = {
                alignmentPeriod    = "60s"
                perSeriesAligner   = "ALIGN_PERCENTILE_95"
                crossSeriesReducer = "REDUCE_MAX"
              }
            }
          }
        }]
        yAxis = { label = "milliseconds", scale = "LINEAR" }
      }
    },
    {
      title = "Billable instance time"
      xyChart = {
        dataSets = [{
          plotType = "LINE"
          timeSeriesQuery = {
            timeSeriesFilter = {
              filter = "metric.type=\"run.googleapis.com/container/billable_instance_time\" AND ${local.metric_filter}"
              aggregation = {
                alignmentPeriod    = "60s"
                perSeriesAligner   = "ALIGN_RATE"
                crossSeriesReducer = "REDUCE_SUM"
              }
            }
          }
        }]
        yAxis = { label = "billable seconds/second", scale = "LINEAR" }
      }
    }
  ]
}

resource "google_monitoring_dashboard" "service" {
  project = var.project_id
  dashboard_json = jsonencode({
    displayName = "NailSize ${var.environment} service"
    gridLayout = {
      columns = 2
      widgets = local.dashboard_widgets
    }
  })
}
