include "env" {
  path   = find_in_parent_folders()
  expose = true
}

terraform {
  source = "../../../modules//lambda"
}

dependency "llm" {
  config_path = "../llm"
  mock_outputs = {
    llm_provider = "bedrock"
    llm_model    = "bedrock/anthropic.claude-sonnet-4-6-v1:0"
    lambda_env = {
      LLM_MODEL          = "bedrock/anthropic.claude-sonnet-4-6-v1:0"
      LLM_PROVIDER       = "bedrock"
      SLACK_SECRET_NAME  = "mock/slack"
      OPENAI_SECRET_NAME = ""
      GEMINI_SECRET_NAME = ""
    }
    secrets_arns = ["arn:aws:secretsmanager:us-east-1:123456789012:secret:mock"]
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

dependency "logs" {
  config_path = "../logs"
  mock_outputs = {
    log_group_name = "/eks/mock/apps"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

inputs = {
  llm_provider         = dependency.llm.outputs.llm_provider
  llm_env              = dependency.llm.outputs.lambda_env
  llm_secrets_arns     = dependency.llm.outputs.secrets_arns
  dynamodb_table_name  = dependency.dynamodb.outputs.incidents_table_name
  dynamodb_table_arn   = dependency.dynamodb.outputs.incidents_table_arn
  cloudwatch_log_group = dependency.logs.outputs.log_group_name

  # Absolute path to /lambda in the repo, computed from where this
  # terragrunt.hcl lives. Terragrunt copies the module source into
  # .terragrunt-cache/HASH/HASH/, so any relative path from path.module
  # inside the module points at a phantom location.
  #   get_terragrunt_dir() = <repo>/infra/envs/dev/lambda
  #   ../../../../lambda  = <repo>/lambda
  lambda_source_root = "${get_terragrunt_dir()}/../../../../lambda"
}
