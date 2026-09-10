#!/usr/bin/env bash
# Bootstrap ArgoCD + Argo Rollouts on a Kubernetes cluster (kind or EKS)
set -euo pipefail

ARGOCD_VERSION="v3.0.0"
ROLLOUTS_VERSION="v1.8.0"

echo "==> Installing ArgoCD ${ARGOCD_VERSION}"
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd \
  -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"

echo "==> Waiting for ArgoCD server to be ready"
kubectl rollout status deploy/argocd-server -n argocd --timeout=120s

# ── ArgoCD v3 no longer auto-creates argocd-initial-admin-secret, and the
# built-in cluster destination is no longer implicit either. Seed both here
# so the CD workflow (`kubectl get secret argocd-initial-admin-secret`) and
# the ApplicationSet (`destination.server: https://kubernetes.default.svc`)
# both keep working out of the box.
echo "==> Seeding ArgoCD admin password + in-cluster destination"
if ! kubectl -n argocd get secret argocd-initial-admin-secret >/dev/null 2>&1; then
  ADMIN_PW=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)
  ADMIN_HASH=$(kubectl -n argocd exec deploy/argocd-server -- \
    argocd account bcrypt --password "$ADMIN_PW")
  kubectl -n argocd patch secret argocd-secret --type merge -p \
    "{\"stringData\":{\"admin.password\":\"$ADMIN_HASH\",\"admin.passwordMtime\":\"$(date -u +%FT%TZ)\"}}"
  kubectl -n argocd create secret generic argocd-initial-admin-secret \
    --from-literal=password="$ADMIN_PW"
  kubectl -n argocd rollout restart deploy/argocd-server
  kubectl -n argocd rollout status deploy/argocd-server --timeout=120s
fi

kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Secret
metadata:
  name: in-cluster
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: cluster
type: Opaque
stringData:
  name: in-cluster
  server: https://kubernetes.default.svc
  config: |
    {"tlsClientConfig":{"insecure":false}}
YAML

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
