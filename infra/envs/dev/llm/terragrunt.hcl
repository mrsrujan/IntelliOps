include "env" {
  path   = find_in_parent_folders()
  expose = true
}

terraform {
  source = "../../../modules//llm"
}

# Sensitive inputs come from environment variables, never git.
# Set before apply, e.g.:
#   export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
#   export TF_VAR_llm_provider=openai
#   export TF_VAR_openai_api_key=sk-...
inputs = {
  slack_webhook_url = get_env("SLACK_WEBHOOK_URL", "")
}
