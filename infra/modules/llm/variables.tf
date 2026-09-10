variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "llm_provider" {
  type        = string
  default     = "bedrock"
  description = "LLM backend: bedrock, openai, or gemini"

  validation {
    condition     = contains(["bedrock", "openai", "gemini"], var.llm_provider)
    error_message = "llm_provider must be one of: bedrock, openai, gemini"
  }
}

variable "llm_model" {
  type        = string
  default     = "bedrock/us.anthropic.claude-sonnet-4-6"
  description = "Model identifier passed to LiteLLM. Bedrock Sonnet 4.6 is only available via the us.* inference profile."
}

variable "openai_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "gemini_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "slack_webhook_url" {
  type      = string
  sensitive = true
  default   = ""
}
