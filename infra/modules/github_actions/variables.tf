variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "github_repository" {
  type        = string
  description = "GitHub repo the workflows run in, in owner/name form. The IAM role trust policy only accepts OIDC tokens whose `repository` claim matches this exact value."
  default     = "mrsrujan/IntelliOps"
}

variable "eks_cluster_name" {
  type        = string
  description = "EKS cluster name — an Access Entry is created so the GitHub Actions role can call the K8s API (used by the CD workflow)."
}
