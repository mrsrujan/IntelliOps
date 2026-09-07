"""Slack notifications for remediation outcomes."""

import json
import logging
import os

import boto3
import requests

logger = logging.getLogger(__name__)

_webhook_url = ""
_secret_name = os.environ.get("SLACK_SECRET_NAME", "")
if _secret_name:
    try:
        _resp = boto3.client("secretsmanager").get_secret_value(SecretId=_secret_name)
        _webhook_url = json.loads(_resp["SecretString"]).get("webhook_url", "")
    except Exception as e:
        logger.warning(f"slack_webhook_load_failed: {e}")


def _post(payload: dict) -> None:
    if not _webhook_url:
        logger.warning("slack_skipped no_webhook")
        return
    try:
        r = requests.post(_webhook_url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"slack_post_failed: {e}")


def notify_success(anomaly: dict, result: dict, incident_id: str) -> None:
    _post({
        "text": f"✅ Auto-remediation on {anomaly['service']}",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"✅ {result['action']} — {anomaly['service']}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Incident*\n`{incident_id}`"},
                    {"type": "mrkdwn", "text": f"*Trigger*\n{anomaly['anomaly_type']}"},
                    {"type": "mrkdwn", "text": f"*Target*\n{result.get('target', 'n/a')}"},
                    {"type": "mrkdwn", "text": f"*Time*\n{anomaly['timestamp']}"},
                ],
            },
        ],
    })


def notify_failure(anomaly: dict, error: str, incident_id: str) -> None:
    _post({
        "text": f"❌ Remediation failed on {anomaly['service']}",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"❌ Remediation failed — {anomaly['service']}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Incident*: `{incident_id}`\n*Error*: `{error}`\nHuman intervention required."},
            },
        ],
    })
