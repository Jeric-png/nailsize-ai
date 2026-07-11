mock_provider "google" {}

variables {
  project_id  = "nailsize-staging-123"
  environment = "staging"
  region      = "asia-southeast1"
}

run "valid_prerequisites" {
  command = apply

  assert {
    condition     = google_artifact_registry_repository.inference.repository_id == "nailsize-staging-inference"
    error_message = "The registry must be isolated by environment."
  }

  assert {
    condition     = google_service_account.runtime.account_id == "nailsize-staging-runtime"
    error_message = "The runtime identity must be isolated by environment."
  }

  assert {
    condition     = length(google_project_service.required) == 4
    error_message = "Every API required by the runtime stack must be enabled."
  }
}

run "rejects_unapproved_environment" {
  command = plan

  variables {
    environment = "development"
  }

  expect_failures = [var.environment]
}
