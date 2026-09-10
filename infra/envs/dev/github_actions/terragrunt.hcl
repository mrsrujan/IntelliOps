include "env" {
  path   = find_in_parent_folders()
  expose = true
}

terraform {
  source = "../../../modules//github_actions"
}

dependency "eks" {
  config_path = "../eks"
  mock_outputs = {
    cluster_name = "intelliops-dev"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

# github_repository defaults to `mrsrujan/IntelliOps` in the module; override
# here (or via TF_VAR_github_repository) if you forked or renamed the repo.
inputs = {
  eks_cluster_name = dependency.eks.outputs.cluster_name
}
