"""
Rollback approval requester.

Triggered by a DeployRegression anomaly on SNS. Posts an interactive Slack
message with Approve / Reject buttons — the actual rollback only runs when
a human clicks Approve, which round-trips through API Gateway to
rollback_execute.
"""

import json
import logging
import os
import uuid
from datetime import datetime

import boto3
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TABLE = os.environ["DYNAMODB_TABLE"]
APPS_NAMESPACE = os.environ.get("APPS_NAMESPACE", "apps-dev")

_table = boto3.resource("dynamodb").Table(TABLE)
_webhook_url = ""

try:
    _resp = boto3.client("secretsmanager").get_secret_value(
        SecretId=os.environ["SLACK_SECRET_NAME"]
    )
    _webhook_url = json.loads(_resp["SecretString"])["webhook_url"]
except Exception as e:
    logger.warning(f"slack_webhook_load_failed: {e}")


def lambda_handler(event, context):
    anomaly = _parse_anomaly(event)

    # Only DeployRegression triggers a rollback approval — everything else is
    # handled by the auto-remediator or is RCA-only.
    if anomaly["anomaly_type"] != "DeployRegression":
        logger.info(f"skip_non_regression type={anomaly['anomaly_type']}")
        return {"statusCode": 200, "skipped": True}

    incident_id = f"rb-{uuid.uuid4().hex[:12]}"
    service = anomaly["service"]
    argocd_app = f"{service}-dev"  # matches ApplicationSet naming

    _table.put_item(Item={
        "incident_id": incident_id,
        "timestamp": datetime.utcnow().isoformat(),
        "service": service,
        "anomaly_type": anomaly["anomaly_type"],
        "action_taken": "rollback_requested",
        "resolution_status": "pending_approval",
        "argocd_app": argocd_app,
    })

    _post_approval_message(anomaly, incident_id, argocd_app)
    return {"statusCode": 200, "incident_id": incident_id}


def _parse_anomaly(event: dict) -> dict:
    if "Records" in event and event["Records"][0].get("Sns"):
        msg = json.loads(event["Records"][0]["Sns"]["Message"])
    else:
        msg = event

    if "AlarmName" in msg:
        parts = msg["AlarmName"].split("-", 3)
        return {
            "service": parts[3] if len(parts) > 3 else "unknown",
            "anomaly_type": parts[2] if len(parts) > 2 else "DeployRegression",
            "metric": msg.get("Trigger", {}).get("MetricName") or msg["AlarmName"],
            "timestamp": msg.get("StateChangeTime", datetime.utcnow().isoformat()),
        }

    return {
        "service": msg.get("service", "unknown"),
        "anomaly_type": msg.get("anomaly_type", "DeployRegression"),
        "metric": msg.get("metric"),
        "timestamp": msg.get("timestamp", datetime.utcnow().isoformat()),
    }


def _post_approval_message(anomaly: dict, incident_id: str, argocd_app: str) -> None:
    if not _webhook_url:
        logger.warning("slack_skipped no_webhook_configured")
        return

    # `value` is round-tripped verbatim in Slack's callback — encode what
    # rollback_execute needs to act on the click.
    payload_value = json.dumps({
        "incident_id": incident_id,
        "argocd_app": argocd_app,
        "service": anomaly["service"],
    })

    payload = {
        "text": f"⚠ Approve rollback for {anomaly['service']}?",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"⚠ DeployRegression — {anomaly['service']}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Incident*\n`{incident_id}`"},
                    {"type": "mrkdwn", "text": f"*ArgoCD app*\n`{argocd_app}`"},
                    {"type": "mrkdwn", "text": f"*Metric*\n{anomaly.get('metric', 'n/a')}"},
                    {"type": "mrkdwn", "text": f"*Detected*\n{anomaly['timestamp']}"},
                ],
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "style": "primary",
                        "text": {"type": "plain_text", "text": "✅ Approve rollback"},
                        "action_id": "rollback_approve",
                        "value": payload_value,
                    },
                    {
                        "type": "button",
                        "style": "danger",
                        "text": {"type": "plain_text", "text": "❌ Reject"},
                        "action_id": "rollback_reject",
                        "value": payload_value,
                    },
                ],
            },
        ],
    }

    r = requests.post(_webhook_url, json=payload, timeout=10)
    r.raise_for_status()
    logger.info(f"approval_posted incident={incident_id} app={argocd_app}")
