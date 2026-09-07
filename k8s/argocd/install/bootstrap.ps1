# Bootstrap ArgoCD + Argo Rollouts on a Kubernetes cluster (kind or EKS)
$ErrorActionPreference = "Stop"

$ARGOCD_VERSION = "v2.12.0"
$ROLLOUTS_VERSION = "v1.7.2"

Write-Host "==> Installing ArgoCD $ARGOCD_VERSION"
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"

Write-Host "==> Waiting for ArgoCD server to be ready"
kubectl rollout status deploy/argocd-server -n argocd --timeout=120s

Write-Host "==> Installing Argo Rollouts $ROLLOUTS_VERSION"
kubectl create namespace argo-rollouts --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argo-rollouts -f "https://github.com/argoproj/argo-rollouts/releases/download/${ROLLOUTS_VERSION}/install.yaml"

Write-Host "==> Waiting for Argo Rollouts controller to be ready"
kubectl rollout status deploy/argo-rollouts -n argo-rollouts --timeout=120s

Write-Host "==> Applying ArgoCD Project and Applications"
kubectl apply -f "$PSScriptRoot/../projects/"

# Substitute ACCOUNT_ID_PLACEHOLDER in ArgoCD app manifests at apply time
$AccountId = (aws sts get-caller-identity --query Account --output text).Trim()
$TmpDir = New-Item -ItemType Directory -Path (Join-Path $env:TEMP "intelliops-apps-$(Get-Random)")
Get-ChildItem "$PSScriptRoot/../apps/*.yaml" | ForEach-Object {
    (Get-Content $_.FullName) -replace 'ACCOUNT_ID_PLACEHOLDER', $AccountId | Set-Content (Join-Path $TmpDir.FullName $_.Name)
}
kubectl apply -f "$($TmpDir.FullName)/"
Remove-Item -Recurse -Force $TmpDir.FullName

Write-Host "`n==> ArgoCD initial admin password:"
$EncodedPassword = kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}'
if ($EncodedPassword) {
    [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($EncodedPassword))
} else {
    Write-Host "Password secret not found or already deleted."
}

Write-Host "`n`n==> Access ArgoCD UI:"
Write-Host "    kubectl port-forward svc/argocd-server -n argocd 8080:443"
Write-Host "    Open: https://localhost:8080  (user: admin)"