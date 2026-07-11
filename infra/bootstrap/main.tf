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
