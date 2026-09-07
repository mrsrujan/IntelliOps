#!/usr/bin/env bash
# Bootstrap ArgoCD + Argo Rollouts on a Kubernetes cluster (kind or EKS)
set -euo pipefail

ARGOCD_VERSION="v2.12.0"
ROLLOUTS_VERSION="v1.7.2"

echo "==> Installing ArgoCD ${ARGOCD_VERSION}"
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd \
  -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"

echo "==> Waiting for ArgoCD server to be ready"
kubectl rollout status deploy/argocd-server -n argocd --timeout=120s

echo "==> Installing Argo Rollouts ${ROLLOUTS_VERSION}"
kubectl create namespace argo-rollouts --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argo-rollouts \
  -f "https://github.com/argoproj/argo-rollouts/releases/download/${ROLLOUTS_VERSION}/install.yaml"

echo "==> Waiting for Argo Rollouts controller to be ready"
kubectl rollout status deploy/argo-rollouts -n argo-rollouts --timeout=120s

echo "==> Applying ArgoCD Project and Applications"
kubectl apply -f "$(dirname "$0")/../projects/"

# Some ArgoCD Applications embed the AWS account ID (for IRSA role ARNs).
# Substitute it at bootstrap time so we never commit the account ID to git.
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
TMPDIR=$(mktemp -d)
for f in "$(dirname "$0")"/../apps/*.yaml; do
  sed "s/ACCOUNT_ID_PLACEHOLDER/${ACCOUNT_ID}/g" "$f" > "$TMPDIR/$(basename "$f")"
done
kubectl apply -f "$TMPDIR/"
rm -rf "$TMPDIR"

echo ""
echo "==> ArgoCD initial admin password:"
kubectl get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath='{.data.password}' | base64 -d
echo ""
echo ""
echo "==> Access ArgoCD UI:"
echo "    kubectl port-forward svc/argocd-server -n argocd 8080:443"
echo "    Open: https://localhost:8080  (user: admin)"
