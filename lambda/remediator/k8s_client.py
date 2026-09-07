"""
EKS auth for the kubernetes Python client.

Generates a bearer token equivalent to `aws eks get-token` using STS presigned
URLs — no extra dependencies beyond boto3, which Lambda already ships.
"""

import base64
import os
import tempfile

import boto3
from botocore.signers import RequestSigner
from kubernetes import client as k8s_client

CLUSTER_NAME = os.environ["EKS_CLUSTER_NAME"]
REGION = os.environ["AWS_REGION_NAME"]

_ca_cert_path: str | None = None


def _get_bearer_token() -> str:
    """Signed STS URL, base64-wrapped — the format EKS expects for auth."""
    session = boto3.Session()
    sts = session.client("sts", region_name=REGION)
    signer = RequestSigner(
        sts.meta.service_model.service_id,
        REGION,
        "sts",
        "v4",
        session.get_credentials(),
        session.events,
    )
    signed_url = signer.generate_presigned_url(
        {
            "method": "GET",
            "url": f"https://sts.{REGION}.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15",
            "body": {},
            "headers": {"x-k8s-aws-id": CLUSTER_NAME},
            "context": {},
        },
        region_name=REGION,
        expires_in=60,
        operation_name="",
    )
    b64 = base64.urlsafe_b64encode(signed_url.encode()).decode().rstrip("=")
    return f"k8s-aws-v1.{b64}"


def _ensure_ca_cert() -> str:
    """Write cluster CA to /tmp once per Lambda cold start."""
    global _ca_cert_path
    if _ca_cert_path is None:
        eks = boto3.client("eks", region_name=REGION)
        cluster = eks.describe_cluster(name=CLUSTER_NAME)["cluster"]
        ca_data = base64.b64decode(cluster["certificateAuthority"]["data"])
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".pem", dir="/tmp")
        f.write(ca_data)
        f.close()
        _ca_cert_path = f.name
    return _ca_cert_path


def _endpoint() -> str:
    eks = boto3.client("eks", region_name=REGION)
    return eks.describe_cluster(name=CLUSTER_NAME)["cluster"]["endpoint"]


def make_api_client() -> k8s_client.ApiClient:
    """Return a kubernetes ApiClient authenticated to the EKS cluster."""
    cfg = k8s_client.Configuration()
    cfg.host = _endpoint()
    cfg.ssl_ca_cert = _ensure_ca_cert()
    cfg.verify_ssl = True
    cfg.api_key = {"authorization": f"Bearer {_get_bearer_token()}"}
    return k8s_client.ApiClient(configuration=cfg)
