locals {
  aws_region  = "us-east-1"
  project     = "intelliops"
  environment = get_env("ENVIRONMENT", "dev")
}

remote_state {
  backend = "s3"
  config = {
    bucket         = "${local.project}-tfstate-${local.environment}"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = local.aws_region
    encrypt        = true
    dynamodb_table = "${local.project}-tflock-${local.environment}"
  }
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = "${local.aws_region}"
  default_tags {
    tags = {
      Project     = "${local.project}"
      Environment = "${local.environment}"
      ManagedBy   = "terraform"
    }
  }
}
EOF
}

inputs = {
  aws_region  = local.aws_region
  project     = local.project
  environment = local.environment
}
