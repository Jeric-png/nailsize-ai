resource "google_billing_budget" "project" {
  billing_account = var.billing_account_id
  display_name    = "NailSize ${var.environment} (${var.project_id})"
  ownership_scope = "BILLING_ACCOUNT"
  deletion_policy = "PREVENT"

  budget_filter {
    projects               = ["projects/${data.google_project.current.number}"]
    credit_types_treatment = "INCLUDE_ALL_CREDITS"
  }

  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = tostring(var.monthly_budget_units)
    }
  }

  dynamic "threshold_rules" {
    for_each = toset(var.budget_thresholds)
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }

  all_updates_rule {
    monitoring_notification_channels = var.notification_channel_ids
    disable_default_iam_recipients   = false
    enable_project_level_recipients  = true
  }
}
