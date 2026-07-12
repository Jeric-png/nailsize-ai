mock_provider "google" {}

variables {
  project_id                     = "nailsize-staging-123"
  environment                    = "staging"
  region                         = "asia-southeast1"
  api_domain                     = "api-staging.nailsize.example"
  frontend_origin                = "https://staging.nailsize.example"
  image_uri                      = "asia-southeast1-docker.pkg.dev/nailsize-staging-123/nailsize-staging-inference/inference@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  model_version                  = "candidate-2026-07-12"
  model_sha256                   = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  segmentation_boundary_error_px = 0.5
  max_instances                  = 10
  rate_limit_requests            = 60
  rate_limit_interval_seconds    = 60
  rate_limit_preview             = true
  deletion_protection            = true
}

run "valid_secure_boundary" {
  command = apply

  assert {
    condition     = google_cloud_run_v2_service.inference.ingress == "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
    error_message = "Cloud Run must only accept internal and load-balancer ingress."
  }

  assert {
    condition     = google_cloud_run_v2_service.inference.default_uri_disabled
    error_message = "The bypassable run.app URL must be disabled."
  }

  assert {
    condition     = google_cloud_run_v2_service.inference.template[0].max_instance_request_concurrency == 1
    error_message = "Inference concurrency must remain one request per instance."
  }

  assert {
    condition     = google_compute_backend_service.inference.security_policy == google_compute_security_policy.edge.id
    error_message = "The public backend must be protected by Cloud Armor."
  }

  assert {
    condition     = google_compute_backend_service.inference.log_config[0].enable && google_compute_backend_service.inference.log_config[0].sample_rate == 1
    error_message = "The backend must retain complete native request metadata for operational review."
  }

  assert {
    condition     = google_compute_url_map.http_redirect.default_url_redirect[0].strip_query
    error_message = "HTTP redirects must discard query strings before logging or forwarding."
  }

  assert {
    condition     = one([for rule in google_compute_security_policy.edge.rule : rule.preview if rule.priority == 1000])
    error_message = "The test policy must begin in preview mode."
  }

  assert {
    condition     = google_cloud_run_v2_service.inference.template[0].service_account == "nailsize-staging-runtime@nailsize-staging-123.iam.gserviceaccount.com"
    error_message = "Cloud Run must use the bootstrapped environment-specific runtime identity."
  }

  assert {
    condition = (
      google_cloud_run_v2_job.onnx_benchmark.template[0].task_count == 1 &&
      google_cloud_run_v2_job.onnx_benchmark.template[0].parallelism == 1 &&
      google_cloud_run_v2_job.onnx_benchmark.template[0].template[0].max_retries == 0 &&
      google_cloud_run_v2_job.onnx_benchmark.template[0].template[0].timeout == "300s" &&
      google_cloud_run_v2_job.onnx_benchmark.template[0].template[0].containers[0].resources[0].limits["cpu"] == "2" &&
      google_cloud_run_v2_job.onnx_benchmark.template[0].template[0].containers[0].resources[0].limits["memory"] == "4Gi"
    )
    error_message = "The benchmark job must run once without retries on the exact 2-vCPU/4-GiB contract."
  }
}

run "rejects_mutable_image_tag" {
  command = plan

  variables {
    image_uri = "asia-southeast1-docker.pkg.dev/nailsize-staging-123/nailsize-staging-inference/inference:latest"
  }

  expect_failures = [var.image_uri]
}

run "rejects_cross_environment_repository" {
  command = plan

  variables {
    image_uri = "asia-southeast1-docker.pkg.dev/nailsize-staging-123/nailsize-production-inference/inference@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }

  expect_failures = [
    google_cloud_run_v2_job.onnx_benchmark,
    google_cloud_run_v2_service.inference,
  ]
}

run "rejects_wildcard_frontend" {
  command = plan

  variables {
    frontend_origin = "https://*.nailsize.example"
  }

  expect_failures = [var.frontend_origin]
}

run "rejects_unapproved_environment" {
  command = plan

  variables {
    environment = "development"
  }

  expect_failures = [var.environment]
}

run "rejects_invalid_rate_interval" {
  command = plan

  variables {
    rate_limit_interval_seconds = 45
  }

  expect_failures = [var.rate_limit_interval_seconds]
}

run "enforcement_requires_explicit_switch" {
  command = plan

  variables {
    rate_limit_preview = false
  }

  assert {
    condition     = !one([for rule in google_compute_security_policy.edge.rule : rule.preview if rule.priority == 1000])
    error_message = "The explicit enforcement switch must reach Cloud Armor."
  }
}
