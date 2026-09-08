variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "eks_cluster_name" {
  type = string
}

variable "anomalies_topic_arn" {
  type        = string
  description = "SNS topic from the lambda module — remediation Lambdas subscribe here"
}

variable "dynamodb_table_name" {
  type = string
}

variable "dynamodb_table_arn" {
  type = string
}

variable "shared_secrets_arns" {
  type        = list(string)
  description = "Secret ARNs the remediation Lambdas need to read (Slack webhook, etc.)"
  default     = []
}

variable "slack_webhook_secret_name" {
  type        = string
  description = "Name of the Slack webhook secret (created by the llm module)"
}

variable "slack_signing_secret" {
  type        = string
  sensitive   = true
  default     = ""
  description = "Slack app signing secret — set via TF_VAR_slack_signing_secret"
}

variable "argocd_api_token" {
  type        = string
  sensitive   = true
  default     = ""
  description = "ArgoCD API token — set via TF_VAR_argocd_api_token"
}

variable "argocd_server_url" {
  type        = string
  default     = "https://argocd-server.argocd.svc.cluster.local"
  description = "ArgoCD server URL — internal DNS by default, override for external ALB"
}

variable "apps_namespace" {
  type        = string
  default     = "apps-dev"
}

variable "lambda_source_root" {
  type        = string
  description = "Absolute path to the repo's /lambda directory. Passed from terragrunt.hcl using get_terragrunt_dir() because Terragrunt's module-copy step invalidates relative paths."
}
