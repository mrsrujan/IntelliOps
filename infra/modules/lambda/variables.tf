variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "llm_provider" {
  type = string
}

variable "llm_env" {
  type        = map(string)
  description = "Environment variables from the llm module (model id, secret names)"
}

variable "llm_secrets_arns" {
  type        = list(string)
  description = "Secret ARNs the Lambda needs GetSecretValue on"
}

variable "dynamodb_table_name" {
  type = string
}

variable "dynamodb_table_arn" {
  type = string
}

variable "cloudwatch_log_group" {
  type        = string
  description = "Log group the Lambda queries for RCA context"
}
