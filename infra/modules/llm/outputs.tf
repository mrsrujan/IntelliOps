output "llm_provider" {
  value = var.llm_provider
}

output "llm_model" {
  value = var.llm_model
}

# All secret ARNs the Lambda needs read access to
output "secrets_arns" {
  value = concat(
    [aws_secretsmanager_secret.slack.arn],
    try([aws_secretsmanager_secret.openai[0].arn], []),
    try([aws_secretsmanager_secret.gemini[0].arn], []),
  )
}

# Env vars to inject into the Lambda
output "lambda_env" {
  value = {
    LLM_MODEL             = var.llm_model
    LLM_PROVIDER          = var.llm_provider
    SLACK_SECRET_NAME     = aws_secretsmanager_secret.slack.name
    OPENAI_SECRET_NAME    = try(aws_secretsmanager_secret.openai[0].name, "")
    GEMINI_SECRET_NAME    = try(aws_secretsmanager_secret.gemini[0].name, "")
  }
}
