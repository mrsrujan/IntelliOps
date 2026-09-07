"""
Minimal ArgoCD REST API wrapper for rollback.

The ArgoCD server is a ClusterIP service inside EKS. In the current deploy this
Lambda reaches it via VPC (attach the Lambda to the EKS VPC and use the
argocd-server internal DNS name). If VPC config isn't in place, the client
returns a dry-run result so the audit trail and Slack messaging still work.
"""

import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

ARGOCD_URL = os.environ.get("ARGOCD_SERVER_URL", "")


class ArgoCDClient:
    def __init__(self, token: str):
        self._token = token
        self._base = ARGOCD_URL.rstrip("/")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def get_previous_revision(self, app_name: str) -> int | None:
        """Return the history id of the revision before the current one, or None."""
        try:
            r = requests.get(
                f"{self._base}/api/v1/applications/{app_name}",
                headers=self._headers(),
                timeout=10,
                verify=False,  # internal cert not in Lambda trust store; safe within VPC
            )
            r.raise_for_status()
        except Exception as e:
            logger.warning(f"argocd_unreachable dry_run=true error={e}")
            return None

        history = r.json().get("status", {}).get("history", [])
        if len(history) < 2:
            return None
        return history[-2]["id"]

    def rollback(self, app_name: str, revision_id: int) -> dict:
        try:
            r = requests.post(
                f"{self._base}/api/v1/applications/{app_name}/rollback",
                headers=self._headers(),
                json={"id": revision_id, "prune": False},
                timeout=30,
                verify=False,
            )
            r.raise_for_status()
            return {"status": "ok", "revision_id": revision_id, "response": r.json()}
        except Exception as e:
            logger.warning(f"argocd_rollback_failed dry_run=true error={e}")
            return {"status": "dry_run", "reason": str(e), "revision_id": revision_id}
