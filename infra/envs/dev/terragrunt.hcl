include "root" {
  path = find_in_parent_folders()
}

locals {
  project     = "intelliops"
  environment = "dev"
}

# VPC
dependency "vpc" {
  config_path = "../../../modules/vpc"
  mock_outputs = {
    vpc_id             = "vpc-mock"
    private_subnet_ids = ["subnet-mock-1", "subnet-mock-2", "subnet-mock-3"]
    public_subnet_ids  = ["subnet-mock-pub-1", "subnet-mock-pub-2", "subnet-mock-pub-3"]
    vpc_cidr_block     = "10.0.0.0/16"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

# EKS
dependency "eks" {
  config_path = "../../../modules/eks"
  mock_outputs = {
    cluster_name                       = "intelliops-dev"
    cluster_endpoint                   = "https://mock.eks.amazonaws.com"
    cluster_certificate_authority_data = "bW9jaw=="
    oidc_provider_arn                  = "arn:aws:iam::123456789:oidc-provider/mock"
    cluster_security_group_id          = "sg-mock"
    karpenter_interruption_queue_name  = "intelliops-dev-karpenter"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

# ECR
dependency "ecr" {
  config_path = "../../../modules/ecr"
  mock_outputs = {
    repository_urls = {}
    registry_id     = "123456789"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

inputs = {
  project     = local.project
  environment = local.environment

  # VPC inputs
  vpc_cidr = "10.0.0.0/16"

  # EKS inputs
  vpc_id             = dependency.vpc.outputs.vpc_id
  private_subnet_ids = dependency.vpc.outputs.private_subnet_ids
}
