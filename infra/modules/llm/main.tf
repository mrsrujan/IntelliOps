# Multi-provider LLM configuration.
#
# Provider selection is a deploy-time flag (var.llm_provider). The RCA Lambda
# uses LiteLLM so the actual client code is identical across providers; this
# module only wires up the credentials each provider needs.

# ── Bedrock ──────────────────────────────────────────────────────────────────
# No secret to store; access is granted via IAM policy attached to the Lambda
# execution role (see the lambda module).

# ── OpenAI ───────────────────────────────────────────────────────────────────
resource "aws_secretsmanager_secret" "openai" {
  count       = var.llm_provider == "openai" ? 1 : 0
  name        = "${var.project}/${var.environment}/openai-api-key"
  description = "OpenAI API key for RCA Lambda"
}

resource "aws_secretsmanager_secret_version" "openai" {
  count         = var.llm_provider == "openai" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.openai[0].id
  secret_string = jsonencode({ api_key = var.openai_api_key })
}

# ── Gemini ───────────────────────────────────────────────────────────────────
resource "aws_secretsmanager_secret" "gemini" {
  count       = var.llm_provider == "gemini" ? 1 : 0
  name        = "${var.project}/${var.environment}/gemini-api-key"
  description = "Google Gemini API key for RCA Lambda"
}

resource "aws_secretsmanager_secret_version" "gemini" {
  count         = var.llm_provider == "gemini" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.gemini[0].id
  secret_string = jsonencode({ api_key = var.gemini_api_key })
}

# ── Slack webhook (needed regardless of LLM choice) ──────────────────────────
resource "aws_secretsmanager_secret" "slack" {
  name        = "${var.project}/${var.environment}/slack-webhook"
  description = "Slack incoming webhook URL for RCA notifications"
}

resource "aws_secretsmanager_secret_version" "slack" {
  secret_id     = aws_secretsmanager_secret.slack.id
  secret_string = jsonencode({ webhook_url = var.slack_webhook_url })
}
