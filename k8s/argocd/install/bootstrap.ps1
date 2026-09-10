# Bootstrap ArgoCD + Argo Rollouts on a Kubernetes cluster (kind or EKS)
$ErrorActionPreference = "Stop"

$ARGOCD_VERSION = "v3.0.0"
$ROLLOUTS_VERSION = "v1.8.0"

Write-Host "==> Installing ArgoCD $ARGOCD_VERSION"
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"

Write-Host "==> Waiting for ArgoCD server to be ready"
kubectl rollout status deploy/argocd-server -n argocd --timeout=120s

# ArgoCD v3 no longer auto-creates argocd-initial-admin-secret, and the
# built-in cluster destination is no longer implicit either. Seed both here
# so the CD workflow (`kubectl get secret argocd-initial-admin-secret`) and
# the ApplicationSet (`destination.server: https://kubernetes.default.svc`)
# both keep working out of the box.
Write-Host "==> Seeding ArgoCD admin password + in-cluster destination"
$secretExists = $true
try { kubectl -n argocd get secret argocd-initial-admin-secret 2>&1 | Out-Null; if ($LASTEXITCODE -ne 0) { $secretExists = $false } } catch { $secretExists = $false }
if (-not $secretExists) {
    $bytes = New-Object byte[] 18
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $AdminPw = [Convert]::ToBase64String($bytes) -replace '[/+=]', '' | ForEach-Object { $_.Substring(0,24) }
    $AdminHash = (kubectl -n argocd exec deploy/argocd-server -- argocd account bcrypt --password $AdminPw).Trim()
    $mtime = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $patch = "{`"stringData`":{`"admin.password`":`"$AdminHash`",`"admin.passwordMtime`":`"$mtime`"}}"
    kubectl -n argocd patch secret argocd-secret --type merge -p $patch
    kubectl -n argocd create secret generic argocd-initial-admin-secret --from-literal=password=$AdminPw
    kubectl -n argocd rollout restart deploy/argocd-server
    kubectl -n argocd rollout status deploy/argocd-server --timeout=120s
}

$InClusterSecret = @'
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
'@
$InClusterSecret | kubectl apply -f -

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