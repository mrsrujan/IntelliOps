"""
LLM abstraction via LiteLLM — same code path for Bedrock, OpenAI, Gemini.

Provider is chosen at deploy time via env vars:
  LLM_MODEL           e.g. "bedrock/anthropic.claude-sonnet-4-6-v1:0"
                          "openai/gpt-4o"
                          "gemini/gemini-2.0-pro"
  OPENAI_SECRET_NAME  Secrets Manager entry (only for openai/*)
  GEMINI_SECRET_NAME  Secrets Manager entry (only for gemini/*)

Bedrock uses IAM directly — no API key handling needed.
"""

import json
import logging
import os

import boto3
from litellm import completion

logger = logging.getLogger(__name__)

LLM_MODEL = os.environ["LLM_MODEL"]

_sm = boto3.client("secretsmanager")


def _load_api_key(secret_name: str, key: str) -> None:
    """Load an API key from Secrets Manager into an env var (LiteLLM reads env)."""
    if not secret_name:
        return
    resp = _sm.get_secret_value(SecretId=secret_name)
    payload = json.loads(resp["SecretString"])
    os.environ[key] = payload["api_key"]


# Load provider-specific credentials once at cold start
if LLM_MODEL.startswith("openai/"):
    _load_api_key(os.environ.get("OPENAI_SECRET_NAME", ""), "OPENAI_API_KEY")
elif LLM_MODEL.startswith("gemini/"):
    _load_api_key(os.environ.get("GEMINI_SECRET_NAME", ""), "GEMINI_API_KEY")


def generate_rca(prompt: str) -> str:
    """Ask the configured LLM for a root-cause analysis."""
    logger.info(f"calling llm model={LLM_MODEL} prompt_chars={len(prompt)}")

    response = completion(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.3,
    )

    content = response.choices[0].message.content
    logger.info(f"llm_response chars={len(content)}")
    return content
