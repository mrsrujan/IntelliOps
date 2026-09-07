"""
Posts a formatted incident block to a Slack incoming webhook.
Webhook URL is read from Secrets Manager once at cold start.
"""

import json
import logging
import os

import boto3
import requests

logger = logging.getLogger(__name__)

SLACK_SECRET_NAME = os.environ.get("SLACK_SECRET_NAME", "")

_webhook_url: str = ""
if SLACK_SECRET_NAME:
    try:
        _sm = boto3.client("secretsmanager")
        _resp = _sm.get_secret_value(SecretId=SLACK_SECRET_NAME)
        _webhook_url = json.loads(_resp["SecretString"]).get("webhook_url", "")
    except Exception as e:
        logger.warning(f"could not load slack webhook: {e}")


def post_incident(anomaly: dict, rca: str, incident_id: str) -> None:
    if not _webhook_url:
        logger.warning("slack_skipped no_webhook_configured")
        return

    payload = {
        "text": f"🚨 IntelliOps incident on {anomaly['service']}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 {anomaly['anomaly_type']} — {anomaly['service']}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Incident ID*\n`{incident_id}`"},
                    {"type": "mrkdwn", "text": f"*Detected at*\n{anomaly['timestamp']}"},
                    {"type": "mrkdwn", "text": f"*Metric*\n{anomaly.get('metric') or 'n/a'}"},
                    {"type": "mrkdwn", "text": f"*Model*\n{os.environ.get('LLM_MODEL', 'n/a')}"},
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": rca},
            },
        ],
    }

    try:
        r = requests.post(_webhook_url, json=payload, timeout=10)
        r.raise_for_status()
        logger.info(f"slack_posted status={r.status_code}")
    except Exception as e:
        logger.error(f"slack_post_failed: {e}")
