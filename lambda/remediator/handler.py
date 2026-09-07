"""
Auto-remediation Lambda — routes an SNS anomaly to the correct action.

Actions:
  HighCPU / MemoryPressure    → scale the Rollout up
  RestartRequest              → rollout restart (delete pods gracefully)
  NodeNotReady                → cordon the affected node

Rollback for DeployRegression is handled separately by rollback_request
(needs human approval via Slack).
"""

import json
import logging
import os
import uuid
from datetime import datetime

import actions
import audit
import slack

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

APPS_NAMESPACE = os.environ.get("APPS_NAMESPACE", "apps-dev")


def lambda_handler(event, context):
    try:
        anomaly = _parse_anomaly(event)
    except (KeyError, json.JSONDecodeError, IndexError) as e:
        logger.error(f"bad_event: {e}")
        return {"statusCode": 400, "error": str(e)}

    incident_id = f"rem-{uuid.uuid4().hex[:12]}"
    anomaly_type = anomaly["anomaly_type"]
    service = anomaly["service"]

    logger.info(f"remediating anomaly={anomaly_type} service={service}")

    try:
        if anomaly_type in ("HighCPU", "MemoryPressure"):
            result = actions.scale_rollout(APPS_NAMESPACE, service, target_replicas=10)
        elif anomaly_type == "RestartRequest":
            result = actions.restart_rollout(APPS_NAMESPACE, service)
        elif anomaly_type == "NodeNotReady":
            node_name = anomaly.get("node") or anomaly.get("metric", "").split(":")[-1]
            result = actions.cordon_node(node_name)
        else:
            logger.warning(f"unhandled_anomaly_type: {anomaly_type}")
            return {"statusCode": 200, "skipped": True}

        audit.record(
            incident_id=incident_id,
            service=service,
            anomaly_type=anomaly_type,
            action_taken=result["action"],
            status="auto_remediated",
        )
        slack.notify_success(anomaly, result, incident_id)
        return {"statusCode": 200, "incident_id": incident_id, "result": result}

    except Exception as e:
        logger.exception("remediation_failed")
        audit.record(
            incident_id=incident_id,
            service=service,
            anomaly_type=anomaly_type,
            action_taken="failed",
            status="error",
            error=str(e),
        )
        slack.notify_failure(anomaly, str(e), incident_id)
        return {"statusCode": 500, "error": str(e)}


def _parse_anomaly(event: dict) -> dict:
    if "Records" in event and event["Records"][0].get("Sns"):
        msg = json.loads(event["Records"][0]["Sns"]["Message"])
    else:
        msg = event

    return {
        "service": msg.get("service", "unknown"),
        "anomaly_type": msg.get("anomaly_type", "generic_anomaly"),
        "metric": msg.get("metric"),
        "node": msg.get("node"),
        "timestamp": msg.get("timestamp", datetime.utcnow().isoformat()),
    }
