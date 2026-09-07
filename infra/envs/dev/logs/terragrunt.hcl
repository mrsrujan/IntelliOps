include "env" {
  path   = find_in_parent_folders()   # finds infra/envs/dev/terragrunt.hcl
  expose = true
}

terraform {
  source = "../../../modules//logs"
}

dependency "eks" {
  config_path = "../eks"
  mock_outputs = {
    oidc_provider_arn = "arn:aws:iam::123456789012:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/mock"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

inputs = {
  oidc_provider_arn = dependency.eks.outputs.oidc_provider_arn
}
