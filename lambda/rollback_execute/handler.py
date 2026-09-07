"""
Slack callback target — invoked via API Gateway when a user clicks
"Approve rollback" (or Reject) on the interactive Slack message posted
by rollback_request.

Flow:
  1. Verify Slack signature (HMAC over raw body).
  2. Parse the interactive payload.
  3. If Approve → call ArgoCD rollback API + audit + confirm in Slack.
  4. If Reject  → audit + confirm in Slack.
"""

import base64
import json
import logging
import os
import uuid
from datetime import datetime
from urllib.parse import parse_qs

import boto3
import requests

from argocd_client import ArgoCDClient
from slack_sig import verify

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TABLE = os.environ["DYNAMODB_TABLE"]
_table = boto3.resource("dynamodb").Table(TABLE)
_sm = boto3.client("secretsmanager")

_signing_secret = ""
_argocd_token = ""
_webhook_url = ""


def _load_secrets() -> None:
    global _signing_secret, _argocd_token, _webhook_url
    if _signing_secret:
        return
    _signing_secret = json.loads(
        _sm.get_secret_value(SecretId=os.environ["SLACK_SIGNING_SECRET_NAME"])["SecretString"]
    )["signing_secret"]
    _argocd_token = json.loads(
        _sm.get_secret_value(SecretId=os.environ["ARGOCD_TOKEN_SECRET_NAME"])["SecretString"]
    )["token"]
    _webhook_url = json.loads(
        _sm.get_secret_value(SecretId=os.environ["SLACK_SECRET_NAME"])["SecretString"]
    )["webhook_url"]


def lambda_handler(event, context):
    _load_secrets()

    # API Gateway v2 delivers the raw body as `body`; may be base64-encoded
    body = event.get("body", "") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode()

    headers = {k.lower(): v for k, v in event.get("headers", {}).items()}
    ts = headers.get("x-slack-request-timestamp", "")
    sig = headers.get("x-slack-signature", "")

    if not verify(body, ts, sig, _signing_secret):
        logger.warning("slack_signature_invalid")
        return {"statusCode": 401, "body": "invalid signature"}

    parsed = parse_qs(body)
    if "payload" not in parsed:
        return {"statusCode": 400, "body": "missing payload"}

    payload = json.loads(parsed["payload"][0])
    action = payload["actions"][0]
    action_id = action["action_id"]
    action_value = json.loads(action["value"])
    user = payload.get("user", {}).get("username", "unknown")

    incident_id = action_value["incident_id"]
    argocd_app = action_value["argocd_app"]
    service = action_value["service"]

    audit_id = f"rbx-{uuid.uuid4().hex[:12]}"

    if action_id == "rollback_reject":
        _record(audit_id, service, "rollback_rejected", "rejected", user, argocd_app)
        _reply(payload["response_url"], f"❌ Rollback rejected for `{argocd_app}` by <@{user}> — incident `{incident_id}`.")
        return {"statusCode": 200, "body": ""}

    # Approve path
    argocd = ArgoCDClient(_argocd_token)
    revision_id = argocd.get_previous_revision(argocd_app)
    if revision_id is None:
        _record(audit_id, service, "rollback_no_history", "error", user, argocd_app)
        _reply(payload["response_url"], f"⚠ Could not find a previous revision for `{argocd_app}`.")
        return {"statusCode": 200, "body": ""}

    result = argocd.rollback(argocd_app, revision_id)
    status = "rolled_back" if result["status"] == "ok" else "dry_run"
    _record(audit_id, service, f"rollback_to_rev_{revision_id}", status, user, argocd_app)

    msg = (
        f"✅ Rollback executed on `{argocd_app}` (revision {revision_id}) — "
        f"approved by <@{user}>, incident `{incident_id}`."
        if status == "rolled_back"
        else f"🧪 Dry-run rollback recorded for `{argocd_app}` — approved by <@{user}>. "
             "ArgoCD not reachable from Lambda; add VPC config to enable live rollback."
    )
    _reply(payload["response_url"], msg)
    return {"statusCode": 200, "body": ""}


def _record(audit_id: str, service: str, action: str, status: str, user: str, app: str) -> None:
    _table.put_item(Item={
        "incident_id": audit_id,
        "timestamp": datetime.utcnow().isoformat(),
        "service": service,
        "anomaly_type": "DeployRegression",
        "action_taken": action,
        "resolution_status": status,
        "approved_by": user,
        "argocd_app": app,
    })


def _reply(response_url: str, text: str) -> None:
    """Update the original Slack message so buttons disappear after action."""
    try:
        requests.post(response_url, json={"text": text, "replace_original": True}, timeout=10)
    except Exception as e:
        logger.warning(f"slack_reply_failed: {e}")
