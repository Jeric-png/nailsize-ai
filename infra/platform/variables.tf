variable "project_id" {
  description = "Google Cloud project that owns this environment."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a valid Google Cloud project ID."
  }
}

variable "environment" {
  description = "Isolated deployable environment."
  type        = string

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "region" {
  description = "Region for Cloud Run and the serverless NEG."
  type        = string

  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]+$", var.region))
    error_message = "region must be a Google Cloud region such as asia-southeast1."
  }
}

variable "api_domain" {
  description = "DNS name that will point to the load balancer, without a scheme or path."
  type        = string

  validation {
    condition     = length(var.api_domain) <= 253 && can(regex("^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z]{2,63}$", var.api_domain))
    error_message = "api_domain must be a lowercase fully qualified domain name."
  }
}

variable "frontend_origin" {
  description = "Exact HTTPS frontend origin allowed by CORS."
  type        = string

  validation {
    condition     = can(regex("^https://[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::[0-9]{1,5})?$", var.frontend_origin))
    error_message = "frontend_origin must be one exact HTTPS origin without a path."
  }
}

variable "image_uri" {
  description = "Immutable inference container URI, pinned by sha256 digest."
  type        = string

  validation {
    condition     = can(regex("^[^[:space:]]+@sha256:[0-9a-f]{64}$", var.image_uri))
    error_message = "image_uri must be pinned with an @sha256 digest."
  }
}

variable "model_version" {
  description = "Immutable, human-readable model release identifier."
  type        = string

  validation {
    condition     = length(trimspace(var.model_version)) > 0
    error_message = "model_version must not be empty."
  }
}

variable "model_sha256" {
  description = "Expected SHA-256 checksum of the ONNX model bundled in the image."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-f]{64}$", var.model_sha256))
    error_message = "model_sha256 must be 64 lowercase hexadecimal characters."
  }
}

variable "segmentation_boundary_error_px" {
  description = "Validated segmentation boundary error used by measurement uncertainty."
  type        = number

  validation {
    condition     = var.segmentation_boundary_error_px > 0
    error_message = "segmentation_boundary_error_px must be greater than zero."
  }
}

variable "max_instances" {
  description = "Load-tested hard maximum for Cloud Run instances."
  type        = number

  validation {
    condition     = var.max_instances >= 1 && var.max_instances <= 100 && floor(var.max_instances) == var.max_instances
    error_message = "max_instances must be an integer from 1 through 100."
  }
}

variable "rate_limit_requests" {
  description = "Staging-derived requests allowed per client IP in each interval."
  type        = number

  validation {
    condition     = var.rate_limit_requests >= 1 && floor(var.rate_limit_requests) == var.rate_limit_requests
    error_message = "rate_limit_requests must be a positive integer."
  }
}

variable "rate_limit_interval_seconds" {
  description = "Cloud Armor rate-limit interval in seconds."
  type        = number

  validation {
    condition     = contains([10, 30, 60, 120, 180, 240, 300, 600, 900, 1200, 1800, 2700, 3600], var.rate_limit_interval_seconds)
    error_message = "rate_limit_interval_seconds must be a Cloud Armor-supported interval."
  }
}

variable "rate_limit_preview" {
  description = "Whether the rate rule only logs matches; use true until staging evidence approves enforcement."
  type        = bool
}

variable "deletion_protection" {
  description = "Whether Terraform must refuse deletion of the Cloud Run service."
  type        = bool
}
