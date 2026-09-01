include "env" {
  path   = find_in_parent_folders()   # finds infra/envs/dev/terragrunt.hcl
  expose = true
}

terraform {
  source = "../../../modules//vpc"
}

inputs = {
  vpc_cidr = "10.0.0.0/16"
}
