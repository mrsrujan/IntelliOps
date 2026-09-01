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
kubectl apply -f "$(dirname "$0")/../apps/applicationset.yaml"

echo ""
echo "==> ArgoCD initial admin password:"
kubectl get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath='{.data.password}' | base64 -d
echo ""
echo ""
echo "==> Access ArgoCD UI:"
echo "    kubectl port-forward svc/argocd-server -n argocd 8080:443"
echo "    Open: https://localhost:8080  (user: admin)"
