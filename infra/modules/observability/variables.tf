variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "eks_cluster_name" {
  type = string
}

variable "log_group_name" {
  type        = string
  description = "CloudWatch Log Group Fluent Bit ships to (from the logs module)"
}

variable "anomalies_topic_arn" {
  type        = string
  description = "SNS topic all alarms publish to (from the lambda module)"
}

variable "apps_namespace" {
  type    = string
  default = "apps-dev"
}

variable "services" {
  type        = list(string)
  default     = ["payment-service", "order-service"]
  description = "Services to monitor. Each gets its own set of alarms."
}
