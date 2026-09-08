variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "Passed to the exec-based helm/kubernetes provider auth so aws eks get-token targets the right region"
}
