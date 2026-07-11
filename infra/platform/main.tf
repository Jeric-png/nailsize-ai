locals {
  prefix = "nailsize-${var.environment}"
  enabled_services = toset([
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "run.googleapis.com",
  ])
}

resource "google_project_service" "required" {
  for_each = local.enabled_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "inference" {
  project       = var.project_id
  location      = var.region
  repository_id = "${local.prefix}-inference"
  description   = "Immutable NailSize inference images for ${var.environment}"
  format        = "DOCKER"

  depends_on = [google_project_service.required]
}

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "${local.prefix}-runtime"
  display_name = "NailSize ${var.environment} inference runtime"
  description  = "Runtime identity intentionally granted no project roles; model assets are bundled in the image."

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service" "inference" {
  project              = var.project_id
  name                 = "${local.prefix}-inference"
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  launch_stage         = "BETA"
  default_uri_disabled = true
  deletion_protection  = var.deletion_protection

  template {
    service_account                  = google_service_account.runtime.email
    timeout                          = "15s"
    max_instance_request_concurrency = 1

    scaling {
      min_instance_count = 1
      max_instance_count = var.max_instances
    }

    containers {
      name  = "inference"
      image = var.image_uri

      ports {
        name           = "http1"
        container_port = 8080
      }

      env {
        name  = "DEPLOYMENT_ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "ALLOWED_ORIGINS"
        value = var.frontend_origin
      }
      env {
        name  = "MODEL_PATH"
        value = "models/nail-segmentation.onnx"
      }
      env {
        name  = "MODEL_SHA256"
        value = var.model_sha256
      }
      env {
        name  = "MODEL_VERSION"
        value = var.model_version
      }
      env {
        name  = "SEGMENTATION_BOUNDARY_ERROR_PX"
        value = tostring(var.segmentation_boundary_error_px)
      }
      env {
        name  = "HAND_LANDMARKER_PATH"
        value = "models/hand_landmarker.task"
      }
      env {
        name  = "HAND_LANDMARKER_SHA256"
        value = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "4Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      startup_probe {
        failure_threshold = 30
        period_seconds    = 2
        timeout_seconds   = 1

        http_get {
          path = "/ready"
          port = 8080
        }
      }

      liveness_probe {
        failure_threshold = 3
        period_seconds    = 10
        timeout_seconds   = 1

        http_get {
          path = "/health"
          port = 8080
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_artifact_registry_repository.inference,
    google_project_service.required,
  ]
}

# The load balancer cannot authenticate to a serverless NEG. Public invocation is
# therefore allowed at IAM while ingress and the disabled default URL constrain
# internet traffic to the Cloud Armor-protected load balancer.
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.inference.location
  name     = google_cloud_run_v2_service.inference.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_compute_region_network_endpoint_group" "inference" {
  project               = var.project_id
  name                  = "${local.prefix}-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.inference.name
  }

  depends_on = [google_project_service.required]
}

resource "google_compute_security_policy" "edge" {
  project     = var.project_id
  name        = "${local.prefix}-edge"
  description = "Rate controls for the NailSize ${var.environment} inference endpoint"
  type        = "CLOUD_ARMOR"

  rule {
    action      = "throttle"
    priority    = 1000
    description = "Per-client throttle derived from staging evidence"
    preview     = var.rate_limit_preview

    match {
      versioned_expr = "SRC_IPS_V1"

      config {
        src_ip_ranges = ["*"]
      }
    }

    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"

      rate_limit_threshold {
        count        = var.rate_limit_requests
        interval_sec = var.rate_limit_interval_seconds
      }
    }
  }

  rule {
    action      = "allow"
    priority    = 2147483647
    description = "Required default rule"

    match {
      versioned_expr = "SRC_IPS_V1"

      config {
        src_ip_ranges = ["*"]
      }
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_compute_backend_service" "inference" {
  project               = var.project_id
  name                  = "${local.prefix}-backend"
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  security_policy       = google_compute_security_policy.edge.id
  timeout_sec           = 15

  backend {
    group = google_compute_region_network_endpoint_group.inference.id
  }

  log_config {
    enable      = true
    sample_rate = 1
  }
}

resource "google_compute_managed_ssl_certificate" "api" {
  project = var.project_id
  name    = "${local.prefix}-api"

  managed {
    domains = [var.api_domain]
  }

  depends_on = [google_project_service.required]
}

resource "google_compute_global_address" "api" {
  project = var.project_id
  name    = "${local.prefix}-api"

  depends_on = [google_project_service.required]
}

resource "google_compute_url_map" "api" {
  project         = var.project_id
  name            = "${local.prefix}-api"
  default_service = google_compute_backend_service.inference.id
}

resource "google_compute_target_https_proxy" "api" {
  project          = var.project_id
  name             = "${local.prefix}-api"
  url_map          = google_compute_url_map.api.id
  ssl_certificates = [google_compute_managed_ssl_certificate.api.id]
}

resource "google_compute_global_forwarding_rule" "https" {
  project               = var.project_id
  name                  = "${local.prefix}-https"
  ip_address            = google_compute_global_address.api.id
  port_range            = "443"
  target                = google_compute_target_https_proxy.api.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

resource "google_compute_url_map" "http_redirect" {
  project = var.project_id
  name    = "${local.prefix}-http-redirect"

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "http_redirect" {
  project = var.project_id
  name    = "${local.prefix}-http-redirect"
  url_map = google_compute_url_map.http_redirect.id
}

resource "google_compute_global_forwarding_rule" "http_redirect" {
  project               = var.project_id
  name                  = "${local.prefix}-http-redirect"
  ip_address            = google_compute_global_address.api.id
  port_range            = "80"
  target                = google_compute_target_http_proxy.http_redirect.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
