"""
Gathers evidence the LLM will reason over:
  - Recent WARN/ERROR log lines from the affected service (CloudWatch Logs Insights)
  - Similar past incidents for the same service (DynamoDB GSI)
"""

import logging
import os
import time
from datetime import datetime, timedelta

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)

LOG_GROUP = os.environ["CLOUDWATCH_LOG_GROUP"]
DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE"]

_logs = boto3.client("logs")
_table = boto3.resource("dynamodb").Table(DYNAMODB_TABLE)


def build_context(anomaly: dict) -> dict:
    service = anomaly["service"]

    recent_errors = _query_logs(service, minutes=30)
    similar_incidents = _query_similar(service, limit=3)

    return {
        "recent_errors": recent_errors,
        "similar_incidents": similar_incidents,
        "time_window_minutes": 30,
    }


def _query_logs(service: str, minutes: int) -> list[dict]:
    """Fetch recent WARN/ERROR log lines for a service via CloudWatch Logs Insights."""
    end_time = int(datetime.utcnow().timestamp())
    start_time = end_time - minutes * 60

    query = f"""
    fields @timestamp, level, message, request_id
    | filter service = '{service}'
    | filter level in ['ERROR', 'WARNING']
    | sort @timestamp desc
    | limit 30
    """

    try:
        started = _logs.start_query(
            logGroupName=LOG_GROUP,
            startTime=start_time,
            endTime=end_time,
            queryString=query,
        )
        query_id = started["queryId"]

        # Poll for completion (max ~15s — Insights is usually much faster)
        for _ in range(15):
            time.sleep(1)
            result = _logs.get_query_results(queryId=query_id)
            if result["status"] in ("Complete", "Failed", "Cancelled"):
                break

        if result["status"] != "Complete":
            logger.warning(f"logs_query_incomplete status={result['status']}")
            return []

        return [
            {field["field"].lstrip("@"): field["value"] for field in row}
            for row in result.get("results", [])
        ]
    except Exception as e:
        logger.warning(f"logs_query_failed: {e}")
        return []


def _query_similar(service: str, limit: int) -> list[dict]:
    """Find recent past incidents for the same service (last 7 days)."""
    try:
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        resp = _table.query(
            IndexName="service-index",
            KeyConditionExpression=Key("service").eq(service) & Key("timestamp").gte(cutoff),
            Limit=limit,
            ScanIndexForward=False,
        )
        return [
            {
                "timestamp": item["timestamp"],
                "anomaly_type": item.get("anomaly_type"),
                "resolution_status": item.get("resolution_status"),
                "rca_summary": item.get("rca_summary", "")[:400],
            }
            for item in resp.get("Items", [])
        ]
    except Exception as e:
        logger.warning(f"similar_incidents_query_failed: {e}")
        return []
