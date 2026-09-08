include "env" {
  path   = find_in_parent_folders()
  expose = true
}

terraform {
  source = "../../../modules//remediation"
}

dependency "eks" {
  config_path = "../eks"
  mock_outputs = {
    cluster_name = "intelliops-dev"
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

dependency "dynamodb" {
  config_path = "../dynamodb"
  mock_outputs = {
    incidents_table_name = "mock-incidents"
    incidents_table_arn  = "arn:aws:dynamodb:us-east-1:123456789012:table/mock"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

dependency "llm" {
  config_path = "../llm"
  mock_outputs = {
    lambda_env   = { SLACK_SECRET_NAME = "mock/slack" }
    secrets_arns = ["arn:aws:secretsmanager:us-east-1:123456789012:secret:mock"]
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

# Sensitive values from environment — never in git.
#   export TF_VAR_slack_signing_secret=<from Slack app config>
#   export TF_VAR_argocd_api_token=<from `argocd account generate-token`>
inputs = {
  eks_cluster_name          = dependency.eks.outputs.cluster_name
  anomalies_topic_arn       = dependency.lambda.outputs.anomalies_topic_arn
  dynamodb_table_name       = dependency.dynamodb.outputs.incidents_table_name
  dynamodb_table_arn        = dependency.dynamodb.outputs.incidents_table_arn
  shared_secrets_arns       = dependency.llm.outputs.secrets_arns
  slack_webhook_secret_name = dependency.llm.outputs.lambda_env.SLACK_SECRET_NAME

  # Absolute path to /lambda in the repo — Terragrunt's module-cache
  # copy invalidates relative paths from within the module.
  lambda_source_root = "${get_terragrunt_dir()}/../../../../lambda"
}
