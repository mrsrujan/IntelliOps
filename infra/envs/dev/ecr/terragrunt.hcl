include "env" {
  path   = find_in_parent_folders()   # finds infra/envs/dev/terragrunt.hcl
  expose = true
}

terraform {
  source = "../../../modules//ecr"
}
