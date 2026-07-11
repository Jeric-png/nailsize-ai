mock_provider "google" {
  mock_data "google_project" {
    defaults = {
      number = "123456789012"
    }
  }
}

variables {
  project_id                             = "nailsize-staging-123"
  environment                            = "staging"
  service_name                           = "nailsize-inference"
  max_instances                          = 10
  notification_channel_ids               = ["projects/nailsize-staging-123/notificationChannels/123456"]
  error_rate_threshold                   = 0.05
  p95_latency_threshold_ms               = 5000
  malformed_uploads_per_minute_threshold = 30
  billing_account_id                     = "ABCDEF-123456-789ABC"
  monthly_budget_units                   = 100
  budget_currency                        = "USD"
  budget_thresholds                      = [0.5, 0.8, 1.0]
}

run "valid_configuration" {
  command = plan
}

run "rejects_unapproved_environment" {
  command = plan

  variables {
    environment = "development"
  }

  expect_failures = [var.environment]
}

run "rejects_missing_notification_channels" {
  command = plan

  variables {
    notification_channel_ids = []
  }

  expect_failures = [var.notification_channel_ids]
}

run "rejects_invalid_error_rate" {
  command = plan

  variables {
    error_rate_threshold = 0
  }

  expect_failures = [var.error_rate_threshold]
}

run "rejects_invalid_instance_cap" {
  command = plan

  variables {
    max_instances = 0
  }

  expect_failures = [var.max_instances]
}

run "rejects_missing_budget" {
  command = plan

  variables {
    monthly_budget_units = 0
  }

  expect_failures = [var.monthly_budget_units]
}

run "rejects_invalid_budget_threshold" {
  command = plan

  variables {
    budget_thresholds = [1.1]
  }

  expect_failures = [var.budget_thresholds]
}
