variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "oidc_provider_arn" {
  type        = string
  description = "OIDC provider ARN from the EKS module output"
}
