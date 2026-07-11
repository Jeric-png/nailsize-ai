# NailSize Cloud Observability

This Terraform module defines privacy-safe Google Cloud observability for one deployed Cloud Run environment. It configures the existing `_Default` log bucket for 30-day retention, four log-based metrics, a service dashboard, four incident policies, and a project-scoped billing budget.

It does not deploy the application and must use separate state for staging and production.
The budget sends notifications; it is not a hard spending cap. The separately reviewed Cloud Run maximum-instance setting is the cost/abuse ceiling.

## Prerequisites

- Terraform `1.15.8` and Google provider `7.x`.
- A deployed Cloud Run service emitting the JSON contract in `docs/observability.md`.
- Logging, Monitoring, Cloud Billing Budget, and Cloud Resource Manager APIs enabled.
- A verified Monitoring notification channel.
- Application Default Credentials with narrowly scoped permissions to manage logging metrics/buckets, dashboards, alert policies, and billing budgets.
- An approved remote state backend. Never commit state or plan files.

## Validate locally

```sh
terraform -chdir=infra/observability fmt -check -recursive
terraform -chdir=infra/observability init -backend=false
terraform -chdir=infra/observability validate
terraform -chdir=infra/observability test
```

## Plan and apply

Supply every required variable through an environment-specific, uncommitted variable file or CI variables. Thresholds and the budget intentionally have no defaults: the operator must enter approved values rather than inheriting guesses.

```sh
terraform -chdir=infra/observability init \
  -backend-config="bucket=<approved-versioned-state-bucket>" \
  -backend-config="prefix=nailsize/<environment>/observability"
terraform -chdir=infra/observability plan -out=<environment>.tfplan
terraform -chdir=infra/observability apply <environment>.tfplan
```

Review the plan for the exact project, service, notification channels, maximum instances, thresholds, currency, and budget before applying. Applying changes external cloud resources and requires an authorized operator. Afterward, record the dashboard and alert-policy outputs plus a sanitized smoke result in `docs/goal-evidence.md`.

## References

- [Cloud Run metric types](https://docs.cloud.google.com/monitoring/api/metrics_gcp_p_z#run)
- [Log-based metric behavior and pricing](https://docs.cloud.google.com/logging/docs/logs-based-metrics)
- [Create alert policies with Terraform](https://docs.cloud.google.com/monitoring/alerts/terraform)
- [Create dashboards by API](https://docs.cloud.google.com/monitoring/dashboards/api-dashboard)
- [Configure log-bucket retention](https://docs.cloud.google.com/logging/docs/buckets)
- [Cloud Billing budgets and permissions](https://docs.cloud.google.com/billing/docs/how-to/budgets)
