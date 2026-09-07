include "env" {
  path   = find_in_parent_folders()
  expose = true
}

terraform {
  source = "../../../modules//observability"
}

dependency "eks" {
  config_path = "../eks"
  mock_outputs = {
    cluster_name = "intelliops-dev"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

dependency "logs" {
  config_path = "../logs"
  mock_outputs = {
    log_group_name = "/eks/mock/apps"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

dependency "lambda" {
  config_path = "../lambda"
  mock_outputs = {
    anomalies_topic_arn = "arn:aws:sns:us-east-1:123456789012:mock-topic"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

inputs = {
  eks_cluster_name    = dependency.eks.outputs.cluster_name
  log_group_name      = dependency.logs.outputs.log_group_name
  anomalies_topic_arn = dependency.lambda.outputs.anomalies_topic_arn
}
