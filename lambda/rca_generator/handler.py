"""
RCA Lambda — triggered by SNS anomaly events.

Flow:
  1. Parse anomaly event from SNS
  2. Build context (recent logs, similar incidents)
  3. Prompt an LLM (via LiteLLM — Bedrock / OpenAI / Gemini)
  4. Persist audit record to DynamoDB
  5. Post incident summary to Slack
"""

import json
import logging
import os
import uuid
from datetime import datetime

import boto3

from context_builder import build_context
from llm_client import generate_rca
from prompt_template import build_prompt
from slack_client import post_incident

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE"]
LLM_MODEL = os.environ["LLM_MODEL"]

_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(DYNAMODB_TABLE)


def lambda_handler(event, context):
    incident_id = f"inc-{uuid.uuid4().hex[:12]}"
    logger.info("event_received", extra={"incident_id": incident_id})

    try:
        anomaly = _parse_anomaly(event)
    except (KeyError, json.JSONDecodeError, IndexError) as e:
        logger.error(f"bad_event: {e} — event={json.dumps(event)[:500]}")
        return {"statusCode": 400, "error": "malformed anomaly event"}

    logger.info(f"processing anomaly service={anomaly['service']} type={anomaly['anomaly_type']}")

    context_data = build_context(anomaly)
    prompt = build_prompt(anomaly, context_data)
    rca = generate_rca(prompt)

    record = {
        "incident_id": incident_id,
        "timestamp": datetime.utcnow().isoformat(),
        "service": anomaly["service"],
        "anomaly_type": anomaly["anomaly_type"],
        "rca_summary": rca,
        "llm_model": LLM_MODEL,
        "resolution_status": "pending",
        "raw_anomaly": json.dumps(anomaly),
    }
    _table.put_item(Item=record)

    post_incident(anomaly, rca, incident_id)

    logger.info(f"incident_processed id={incident_id} llm={LLM_MODEL}")
    return {"statusCode": 200, "incident_id": incident_id}


def _parse_anomaly(event: dict) -> dict:
    """
    Accept either:
      - SNS event  ({"Records": [{"Sns": {"Message": "..."}}]})
      - Direct invoke with the anomaly object as event
    """
    if "Records" in event and event["Records"][0].get("Sns"):
        msg = json.loads(event["Records"][0]["Sns"]["Message"])
    else:
        msg = event

    # Normalise required fields — set sensible defaults if the source is sparse
    return {
        "service": msg.get("service", "unknown"),
        "anomaly_type": msg.get("anomaly_type", "generic_anomaly"),
        "metric": msg.get("metric"),
        "value": msg.get("value"),
        "threshold": msg.get("threshold"),
        "timestamp": msg.get("timestamp", datetime.utcnow().isoformat()),
    }
