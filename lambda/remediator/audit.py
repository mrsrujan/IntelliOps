"""DynamoDB audit writer — shared across all remediation Lambdas."""

import os
from datetime import datetime

import boto3

TABLE = os.environ["DYNAMODB_TABLE"]

_table = boto3.resource("dynamodb").Table(TABLE)


def record(
    incident_id: str,
    service: str,
    anomaly_type: str,
    action_taken: str,
    status: str,
    error: str | None = None,
) -> None:
    item = {
        "incident_id": incident_id,
        "timestamp": datetime.utcnow().isoformat(),
        "service": service,
        "anomaly_type": anomaly_type,
        "action_taken": action_taken,
        "resolution_status": status,
    }
    if error:
        item["error"] = error
    _table.put_item(Item=item)
