"""
The three auto-remediation actions.

Each function returns a dict describing what it did — passed to Slack and
DynamoDB audit.
"""

import logging
from datetime import datetime

from kubernetes import client as k8s_client
from kubernetes.client.rest import ApiException

from k8s_client import make_api_client

logger = logging.getLogger(__name__)


def _rollout_name(service: str) -> str:
    """Argo Rollout follows Helm's release-chart naming: e.g. payment-service-dev-payment-service."""
    return f"{service}-dev-{service}"


def scale_rollout(namespace: str, service: str, target_replicas: int) -> dict:
    """Patch the Argo Rollout's replica count directly."""
    api = k8s_client.CustomObjectsApi(make_api_client())
    name = _rollout_name(service)

    body = {"spec": {"replicas": target_replicas}}
    api.patch_namespaced_custom_object(
        group="argoproj.io",
        version="v1alpha1",
        namespace=namespace,
        plural="rollouts",
        name=name,
        body=body,
    )
    logger.info(f"scaled rollout={name} ns={namespace} replicas={target_replicas}")
    return {
        "action": f"scale_rollout:{target_replicas}",
        "target": name,
        "namespace": namespace,
    }


def restart_rollout(namespace: str, service: str) -> dict:
    """Trigger a rolling restart by patching the Rollout's restartAt annotation."""
    api = k8s_client.CustomObjectsApi(make_api_client())
    name = _rollout_name(service)

    body = {"spec": {"restartAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}}
    api.patch_namespaced_custom_object(
        group="argoproj.io",
        version="v1alpha1",
        namespace=namespace,
        plural="rollouts",
        name=name,
        body=body,
    )
    logger.info(f"restarted rollout={name} ns={namespace}")
    return {
        "action": "restart_rollout",
        "target": name,
        "namespace": namespace,
    }


def cordon_node(node_name: str) -> dict:
    """Mark a node unschedulable so no new pods land on it. Manual drain follows."""
    if not node_name:
        raise ValueError("cordon_node called without a node name")

    core = k8s_client.CoreV1Api(make_api_client())
    try:
        core.patch_node(node_name, {"spec": {"unschedulable": True}})
    except ApiException as e:
        if e.status == 404:
            raise ValueError(f"node not found: {node_name}") from e
        raise

    logger.info(f"cordoned node={node_name}")
    return {
        "action": "cordon_node",
        "target": node_name,
    }
