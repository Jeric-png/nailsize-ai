variable "project_id" {
  description = "Google Cloud project containing the NailSize inference service."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a valid Google Cloud project ID."
  }
}

variable "environment" {
  description = "Deployment environment represented by these resources."
  type        = string

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "service_name" {
  description = "Exact Cloud Run service name."
  type        = string

  validation {
    condition     = can(regex("^[a-z]([a-z0-9-]{0,47}[a-z0-9])?$", var.service_name))
    error_message = "service_name must be a valid Cloud Run service name."
  }
}

variable "max_instances" {
  description = "Cloud Run maximum instance count configured for this environment."
  type        = number

  validation {
    condition     = var.max_instances >= 1 && floor(var.max_instances) == var.max_instances
    error_message = "max_instances must be a positive whole number."
  }
}

variable "notification_channel_ids" {
  description = "Verified Cloud Monitoring notification channel resource IDs."
  type        = list(string)

  validation {
    condition = length(var.notification_channel_ids) > 0 && alltrue([
      for id in var.notification_channel_ids : can(regex("^projects/[^/]+/notificationChannels/[^/]+$", id))
    ])
    error_message = "Provide at least one full projects/.../notificationChannels/... resource ID."
  }
}

variable "error_rate_threshold" {
  description = "Required 5xx request ratio threshold, expressed from 0 to 1."
  type        = number

  validation {
    condition     = var.error_rate_threshold > 0 && var.error_rate_threshold < 1
    error_message = "error_rate_threshold must be greater than 0 and less than 1."
  }
}

variable "p95_latency_threshold_ms" {
  description = "Required p95 request-latency threshold in milliseconds."
  type        = number

  validation {
    condition     = var.p95_latency_threshold_ms > 0
    error_message = "p95_latency_threshold_ms must be positive."
  }
}

variable "malformed_uploads_per_minute_threshold" {
  description = "Required malformed-upload rate that should open an incident."
  type        = number

  validation {
    condition     = var.malformed_uploads_per_minute_threshold > 0
    error_message = "malformed_uploads_per_minute_threshold must be positive."
  }
}

variable "billing_account_id" {
  description = "Billing account ID used for the project-scoped budget."
  type        = string

  validation {
    condition     = can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.billing_account_id))
    error_message = "billing_account_id must use XXXXXX-XXXXXX-XXXXXX format."
  }
}

variable "monthly_budget_units" {
  description = "Required whole-unit monthly budget in budget_currency."
  type        = number

  validation {
    condition     = var.monthly_budget_units > 0 && floor(var.monthly_budget_units) == var.monthly_budget_units
    error_message = "monthly_budget_units must be a positive whole number."
  }
}

variable "budget_currency" {
  description = "ISO 4217 currency matching the billing account."
  type        = string

  validation {
    condition     = can(regex("^[A-Z]{3}$", var.budget_currency))
    error_message = "budget_currency must be a three-letter uppercase ISO 4217 code."
  }
}

variable "budget_thresholds" {
  description = "Explicit current-spend notification thresholds, expressed from 0 to 1."
  type        = list(number)

  validation {
    condition = length(var.budget_thresholds) > 0 && alltrue([
      for threshold in var.budget_thresholds : threshold > 0 && threshold <= 1
    ])
    error_message = "budget_thresholds must contain values greater than 0 and at most 1."
  }
}
