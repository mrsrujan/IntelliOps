# Building IntelliOps on AWS — Windows / PowerShell Edition

A complete, hand-held walkthrough for provisioning the full IntelliOps stack on AWS from a Windows 10 or 11 laptop using PowerShell, running one end-to-end demo, and tearing it down to zero cost.

> **Time to first working demo:** ~50 minutes end-to-end (Windows adds ~10 min of tool installation vs. the Mac/Linux path)
> **Cost for one 2-hour demo session:** ~$1.50
> **Cost left running 24/7:** ~$250/month

---

## Table of Contents

- [Part 1 — Prerequisites Setup](#part-1--prerequisites-setup)
  - [Step 1: Install Required Tools](#step-1-install-required-tools)
  - [Step 2: Verify Tool Installation](#step-2-verify-tool-installation)
- [Part 2 — AWS Account Setup](#part-2--aws-account-setup)
  - [Step 3: Configure AWS Credentials](#step-3-configure-aws-credentials)
  - [Step 4: Create Terraform State Bucket](#step-4-create-terraform-state-bucket)
  - [Step 5: Request Bedrock Model Access](#step-5-request-bedrock-model-access)
- [Part 3 — External Services Setup](#part-3--external-services-setup)
  - [Step 6: Create Slack App](#step-6-create-slack-app)
- [Part 4 — Configuration](#part-4--configuration)
  - [Step 7: Clone the Repository](#step-7-clone-the-repository)
  - [Step 8: Set Environment Variables](#step-8-set-environment-variables)
- [Part 5 — Deploy Infrastructure](#part-5--deploy-infrastructure)
  - [Step 9: Deploy VPC and ECR](#step-9-deploy-vpc-and-ecr)
  - [Step 10: Deploy EKS Cluster](#step-10-deploy-eks-cluster)
  - [Step 11: Deploy Logs and AI Layer](#step-11-deploy-logs-and-ai-layer)
  - [Step 12: Deploy Remediation and Observability](#step-12-deploy-remediation-and-observability)
- [Part 6 — Cluster Setup](#part-6--cluster-setup)
  - [Step 13: Configure kubectl](#step-13-configure-kubectl)
  - [Step 14: Bootstrap ArgoCD and Apps](#step-14-bootstrap-argocd-and-apps)
  - [Step 15: Generate ArgoCD API Token](#step-15-generate-argocd-api-token)
  - [Step 16: Configure Slack Callback URL](#step-16-configure-slack-callback-url)
- [Part 7 — Verify Everything Works](#part-7--verify-everything-works)
  - [Step 17: Check Cluster Health](#step-17-check-cluster-health)
  - [Step 18: Access the UI](#step-18-access-the-ui)
  - [Step 19: Access Grafana](#step-19-access-grafana)
- [Part 8 — Run a Live Demo](#part-8--run-a-live-demo)
  - [Step 20: Trigger a Chaos Test](#step-20-trigger-a-chaos-test)
  - [Step 21: Watch the AI Response](#step-21-watch-the-ai-response)
  - [Step 22: Demo the Rollback Approval Flow](#step-22-demo-the-rollback-approval-flow)
- [Part 9 — Teardown](#part-9--teardown)
  - [Step 23: Destroy Everything](#step-23-destroy-everything)
  - [Step 24: Confirm Zero Recurring Cost](#step-24-confirm-zero-recurring-cost)
- [Appendix A — Troubleshooting](#appendix-a--troubleshooting)
- [Appendix B — Cost Optimisation](#appendix-b--cost-optimisation)
- [Appendix C — What Each Component Does](#appendix-c--what-each-component-does)

---

# Part 1 — Prerequisites Setup

## Step 1: Install Required Tools

**🎯 What we're achieving:** Getting every CLI tool the deployment needs onto your Windows machine. We use `winget` (built into Windows 11 and modern Windows 10) where possible, and direct downloads for tools not yet in the winget catalogue.

### 1a. Open PowerShell as Administrator

Right-click Start → **Windows Terminal (Admin)** or **PowerShell (Admin)**.

Verify you're on PowerShell 5.1 or newer:

```powershell
$PSVersionTable.PSVersion
```

If you see version 5.1, you're fine. For a better experience, install PowerShell 7:

```powershell
winget install --id Microsoft.PowerShell --exact
```

Then close the terminal and open **PowerShell 7** for the rest of the guide.

### 1b. Install core tools via winget

```powershell
winget install --id Amazon.AWSCLI            --exact --accept-source-agreements
winget install --id HashiCorp.Terraform      --exact --accept-source-agreements
winget install --id Kubernetes.kubectl       --exact --accept-source-agreements
winget install --id Helm.Helm                --exact --accept-source-agreements
winget install --id GitHub.cli               --exact --accept-source-agreements
winget install --id Python.Python.3.12       --exact --accept-source-agreements
winget install --id Git.Git                  --exact --accept-source-agreements
```

**⚠ Important — Git for Windows brings bash with it.** Terraform's Lambda build step calls `bash`, which comes from the Git installer. During Git install (if it prompts), pick **"Git from the command line and also from 3rd-party software"** so `bash.exe` ends up in your `PATH`.

### 1c. Install Terragrunt manually

Terragrunt isn't in winget yet. Download the Windows binary directly:

```powershell
$terragruntVersion = "v0.66.9"
$out = "$env:USERPROFILE\bin\terragrunt.exe"
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\bin" | Out-Null
Invoke-WebRequest -Uri "https://github.com/gruntwork-io/terragrunt/releases/download/$terragruntVersion/terragrunt_windows_amd64.exe" -OutFile $out

# Add ~/bin to PATH for this session and permanently for your user
$env:Path += ";$env:USERPROFILE\bin"
[Environment]::SetEnvironmentVariable("Path", $env:Path, "User")
```

**⏱ Time:** ~10 minutes total for all tools
**💰 Cost impact:** $0

---

## Step 2: Verify Tool Installation

**🎯 What we're achieving:** Confirming every tool is on the `PATH` and callable, so the next steps don't fail with "command not found".

Close and reopen your PowerShell window (so PATH changes take effect), then:

```powershell
aws --version                       # aws-cli/2.15+ Windows/10
terraform --version                 # Terraform v1.5+
terragrunt --version                # terragrunt v0.66+
kubectl version --client            # v1.28+
helm version                        # v3.14+
gh --version                        # gh version 2.40+
python --version                    # Python 3.12+
git --version                       # git version 2.42+
bash --version                      # GNU bash, version 5+  ← proves Git bash is on PATH
```

If any command returns "not recognized", close/reopen PowerShell one more time. If it still fails, re-run the winget install for that tool and check for install errors.

**⏱ Time:** ~1 minute
**💰 Cost impact:** $0

---

# Part 2 — AWS Account Setup

## Step 3: Configure AWS Credentials

**🎯 What we're achieving:** Giving your local machine the ability to call AWS APIs. Everything else in the guide flows through these credentials — Terraform, `kubectl`, `argocd`, and the Slack callback URL all depend on this working.

### 3a. Get an Access Key from your AWS account

1. Sign in to **https://console.aws.amazon.com**
2. Top-right dropdown (your name) → **Security credentials**
3. Under **Access keys** → **Create access key** → **CLI use case** → confirm → **Create**
4. Copy the Access Key ID and Secret Access Key (you'll only see the secret this once)

### 3b. Configure the AWS CLI

```powershell
aws configure
```

Answer the prompts:
- AWS Access Key ID: `<paste>`
- AWS Secret Access Key: `<paste>`
- Default region name: `us-east-1`
- Default output format: `json`

### 3c. Verify

```powershell
aws sts get-caller-identity
```

Expected output — a JSON object with your account ID:
```json
{
    "UserId": "AIDA...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/your-name"
}
```

Save the account ID to a PowerShell variable for later:

```powershell
$env:AWS_REGION = "us-east-1"
$env:ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text).Trim()
Write-Host "Working with AWS account: $env:ACCOUNT_ID"
```

**⏱ Time:** ~3 minutes
**💰 Cost impact:** $0

---

## Step 4: Create Terraform State Bucket

**🎯 What we're achieving:** Terragrunt stores state files (which resources it created, what their IDs are) in S3 so multiple deploys stay consistent. This bucket outlives the cluster — you create it once and reuse it across all deploy/destroy cycles.

```powershell
aws s3api create-bucket `
  --bucket intelliops-tfstate-dev `
  --region $env:AWS_REGION

aws s3api put-bucket-versioning `
  --bucket intelliops-tfstate-dev `
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption `
  --bucket intelliops-tfstate-dev `
  --server-side-encryption-configuration '{\"Rules\":[{\"ApplyServerSideEncryptionByDefault\":{\"SSEAlgorithm\":\"AES256\"}}]}'
```

**Notes on PowerShell escaping:** the JSON payload in the last command uses `\"` to escape quotes for PowerShell. If you're on PowerShell 7+, you can also write it as `'@"...json..."@'`.

Verify:

```powershell
aws s3 ls | Select-String intelliops-tfstate-dev
```

**⏱ Time:** ~1 minute
**💰 Cost impact:** ~$0.01/month (bucket + few KB of state files)

---

## Step 5: Request Bedrock Model Access

**🎯 What we're achieving:** Getting Anthropic Claude usable in your account. AWS retired the old "Manage model access" page in 2025 — serverless foundation models are now enabled by default in every commercial region, but **Anthropic models still require a one-time usage form** the first time you invoke them.

1. Go to **https://console.aws.amazon.com/bedrock/** (region: `us-east-1`)
2. Left sidebar → **Chat / Text playground**
3. Pick a model → **Anthropic → Claude Sonnet 4.6** (or latest available)
4. If a "Submit use case details" form appears, fill it in and submit — approval is typically instant for personal accounts
5. Send any test message in the playground to confirm access

**Verify from PowerShell:**

```powershell
aws bedrock list-foundation-models --region us-east-1 `
  --query "modelSummaries[?contains(modelId, 'claude-sonnet-4')].modelId"
```

Should return a JSON list containing the Claude Sonnet model ID.

**⚠ If you're using OpenAI or Gemini instead**, you can skip this step and use your provider's API key in Step 8.

**⏱ Time:** ~2 minutes
**💰 Cost impact:** $0 to grant access. Pay-per-token when invoked (~$0.008 per RCA call).

---

# Part 3 — External Services Setup

## Step 6: Create Slack App

**🎯 What we're achieving:** IntelliOps sends incident narratives and remediation confirmations to Slack. The rollback approval flow needs an interactive Slack app (with signing secret) so the callback can be verified against forgery.

### 6a. Create a workspace channel

Create a channel like `#intelliops-demos` in your Slack workspace.

### 6b. Create the Slack app

1. Go to **https://api.slack.com/apps** → **Create New App** → **From scratch**
2. Name: `IntelliOps`, workspace: your workspace
3. **Incoming Webhooks** (left sidebar) → toggle **On** → **Add New Webhook to Workspace** → pick `#intelliops-demos` → **Allow**
4. Copy the webhook URL — it looks like `https://hooks.slack.com/services/T.../B.../xxx`
5. **Interactivity & Shortcuts** (left sidebar) → toggle **On** → **Request URL** — leave blank for now, we'll come back after Terraform provisions API Gateway
6. **Basic Information** (left sidebar) → scroll to **App Credentials** → copy the **Signing Secret**

### 6c. Save both values into PowerShell variables

```powershell
$env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/T.../B.../xxx"
$env:TF_VAR_slack_signing_secret = "abc123def456..."
```

**⚠ Important:** These need to survive the whole session. If you close PowerShell, re-set them before continuing. For convenience, save them to a file (**do not commit this file**):

```powershell
# Save to a local .env-style file, load with dot-sourcing
@"
`$env:AWS_REGION = 'us-east-1'
`$env:ACCOUNT_ID = '$env:ACCOUNT_ID'
`$env:SLACK_WEBHOOK_URL = '$env:SLACK_WEBHOOK_URL'
`$env:TF_VAR_slack_signing_secret = '$env:TF_VAR_slack_signing_secret'
`$env:TF_VAR_llm_provider = 'bedrock'
`$env:TF_VAR_llm_model = 'bedrock/anthropic.claude-sonnet-4-6-v1:0'
"@ | Out-File "$env:USERPROFILE\.intelliops.ps1" -Encoding utf8

# Later, in a fresh terminal:
. "$env:USERPROFILE\.intelliops.ps1"
```

**⏱ Time:** ~5 minutes
**💰 Cost impact:** $0

---

# Part 4 — Configuration

## Step 7: Clone the Repository

**🎯 What we're achieving:** Getting the IntelliOps source onto your machine. Terraform reads the modules from `infra/modules/`, Terragrunt reads the environment wiring from `infra/envs/dev/`, and the Lambda build reads Python source from `lambda/`.

```powershell
cd C:\Projects
git clone https://github.com/mrsrujan/IntelliOps.git intelliops
cd intelliops
```

Verify the directory structure:

```powershell
Get-ChildItem -Directory
```

You should see: `.github`, `ai`, `docs`, `helm`, `infra`, `k8s`, `lambda`, and files including `README.md`, `construct.md`, `docker-compose.yml`.

**⏱ Time:** ~1 minute
**💰 Cost impact:** $0

---

## Step 8: Set Environment Variables

**🎯 What we're achieving:** Terraform reads sensitive values (LLM provider choice, API keys, Slack signing secret) from `TF_VAR_*` environment variables. Setting them here means they never touch git.

If you saved them in Step 6c, just source the file:

```powershell
. "$env:USERPROFILE\.intelliops.ps1"
```

Otherwise, set each one explicitly:

```powershell
# LLM provider — bedrock is the default and requires NO API key (uses IAM)
$env:TF_VAR_llm_provider = "bedrock"
$env:TF_VAR_llm_model    = "bedrock/anthropic.claude-sonnet-4-6-v1:0"

# ArgoCD API token — leave empty for now, we generate it in Step 15
$env:TF_VAR_argocd_api_token = ""
```

**If you'd rather use OpenAI:**

```powershell
$env:TF_VAR_llm_provider    = "openai"
$env:TF_VAR_llm_model       = "openai/gpt-4o"
$env:TF_VAR_openai_api_key  = "sk-..."     # from https://platform.openai.com/api-keys
```

**Or Gemini:**

```powershell
$env:TF_VAR_llm_provider    = "gemini"
$env:TF_VAR_llm_model       = "gemini/gemini-2.0-pro"
$env:TF_VAR_gemini_api_key  = "AIza..."    # from https://aistudio.google.com/apikey
```

**Verify all env vars are set:**

```powershell
Get-ChildItem env: | Where-Object { $_.Name -match "TF_VAR_|SLACK_|AWS_|ACCOUNT_" }
```

**⏱ Time:** ~2 minutes
**💰 Cost impact:** $0

---

# Part 5 — Deploy Infrastructure

## Step 9: Deploy VPC and ECR

**🎯 What we're achieving:** Building the network foundation (VPC with public/private subnets across 3 AZs, NAT Gateway for outbound, Internet Gateway for the ALB) and the container registry that will hold our Docker images. Everything else depends on these two, so they go first.

```powershell
cd infra\envs\dev\vpc
terragrunt apply
```

Terragrunt prompts to confirm — type `yes`.

**⏱ Time:** ~3 minutes
**Expected output:** `Apply complete! Resources: ~25 added`

```powershell
cd ..\ecr
terragrunt apply
```

**⏱ Time:** ~30 seconds
**Expected output:** `Apply complete! Resources: 6 added` (3 repos × 2 resources)

**💰 Cost impact:** VPC + NAT Gateway kicks in — ~$0.045/hour (~$32/mo if left running).

---

## Step 10: Deploy EKS Cluster

**🎯 What we're achieving:** Building the Kubernetes cluster itself. This is the longest step because AWS is provisioning the managed control plane, node groups, IRSA roles, and installing Karpenter + AWS Load Balancer Controller via Helm.

```powershell
cd ..\eks
terragrunt apply
```

Confirm `yes`. **This will take 15-20 minutes** — go grab a coffee.

While it runs, you can watch progress in the AWS console: **EKS → Clusters → intelliops-dev**.

**Expected output:** `Apply complete! Resources: ~85 added`

**Verify from PowerShell:**

```powershell
aws eks describe-cluster --name intelliops-dev --query "cluster.status"
```

Should return `"ACTIVE"`.

**⏱ Time:** 15-20 minutes
**💰 Cost impact:** EKS control plane starts billing — $0.10/hour (~$73/mo).

---

## Step 11: Deploy Logs and AI Layer

**🎯 What we're achieving:** Now that the cluster exists, we lay down the log pipeline (CloudWatch Log Group + IRSA for Fluent Bit), the streaming layer (Kinesis), audit table (DynamoDB), and the multi-LLM secrets/RCA Lambda.

Each of these is independent and can be applied in any order. They also happen to be cheap or free until invoked.

```powershell
cd ..\logs
terragrunt apply

cd ..\kinesis
terragrunt apply

cd ..\dynamodb
terragrunt apply

cd ..\llm
terragrunt apply

cd ..\lambda
terragrunt apply
```

The `lambda` step is the interesting one — Terraform runs `pip install -r requirements.txt` inside a `bash -c` sub-shell (which is why Git for Windows had to install bash on the PATH). This produces a Lambda deployment zip containing LiteLLM and its dependencies.

**⏱ Time:** ~5 minutes total
**Expected output:** each `terragrunt apply` ends with `Apply complete!`

**💰 Cost impact:**
- Kinesis: ~$22/mo (2 streams × 1 shard × $0.015/hour)
- DynamoDB: $0 until items written (on-demand billing)
- Lambda + Secrets Manager: <$2/mo baseline

---

## Step 12: Deploy Remediation and Observability

**🎯 What we're achieving:** The remaining pieces — remediation Lambdas + API Gateway for Slack callbacks, and CloudWatch Alarms + Container Insights add-on that generates the anomalies which flow through the whole loop.

```powershell
cd ..\remediation
terragrunt apply

cd ..\observability
terragrunt apply
```

**Grab the Slack callback URL now** — you'll paste it into Slack in Step 16:

```powershell
cd ..\remediation
terragrunt output slack_callback_url
```

Copy the URL — it looks like `https://abc123.execute-api.us-east-1.amazonaws.com/slack/rollback`.

**⏱ Time:** ~3 minutes
**💰 Cost impact:** API Gateway HTTP API is pay-per-request (~$0 idle). Container Insights adds ~$3/mo.

---

# Part 6 — Cluster Setup

## Step 13: Configure kubectl

**🎯 What we're achieving:** Telling your local `kubectl` how to talk to the EKS cluster. The `update-kubeconfig` command writes the cluster's certificate authority and API endpoint into `~/.kube/config` and adds an entry that uses your AWS IAM identity for authentication.

```powershell
aws eks update-kubeconfig --name intelliops-dev --region us-east-1
kubectl get nodes
```

**Expected output:** 2 nodes in `Ready` state (the system node group).

```
NAME                          STATUS   ROLES    AGE   VERSION
ip-10-0-11-142.ec2.internal   Ready    <none>   18m   v1.30.0-eks-...
ip-10-0-12-88.ec2.internal    Ready    <none>   18m   v1.30.0-eks-...
```

**⏱ Time:** ~30 seconds
**💰 Cost impact:** $0

---

## Step 14: Bootstrap ArgoCD and Apps

**🎯 What we're achieving:** Installing ArgoCD + Argo Rollouts in the cluster, then applying all the ArgoCD Application manifests (ApplicationSet for the three apps, plus monitoring, fluent-bit, and all Phase 6 security add-ons). ArgoCD then pulls from Git and deploys everything.

The bootstrap script is written in bash, so we run it via `bash.exe` (from Git for Windows):

```powershell
cd ..\..\..\..
bash k8s/argocd/install/bootstrap.sh
```

**What the script does (annotated):**

1. Installs ArgoCD v2.12.0 (creates `argocd` namespace, applies manifests)
2. Installs Argo Rollouts v1.7.2 (creates `argo-rollouts` namespace)
3. Waits for both to be `Available`
4. Applies the ArgoCD Project (`intelliops`)
5. Substitutes `ACCOUNT_ID_PLACEHOLDER` in every ArgoCD app manifest with your real account ID (so IRSA role ARNs resolve correctly)
6. Applies all the Application manifests

**⏱ Time:** ~5 minutes for bootstrap, then ~5 more for ArgoCD to sync everything

**Wait for everything to become Healthy:**

```powershell
kubectl get application -n argocd
```

Keep re-running until every app shows `Synced` + `Healthy`. Typical apps you should see: `payment-service-dev`, `order-service-dev`, `ui-dev`, `monitoring`, `fluent-bit`, `kyverno`, `kyverno-policies`, `falco`, `trivy-operator`, `external-secrets`, `network-policies`.

**💰 Cost impact:** Karpenter provisions additional worker nodes for the security + monitoring pods (~$0.02-0.05/hour extra).

---

## Step 15: Generate ArgoCD API Token

**🎯 What we're achieving:** The rollback-execute Lambda needs an ArgoCD API token to actually roll back applications. We generate one via the ArgoCD CLI and store it in Secrets Manager where the Lambda picks it up on cold start.

### 15a. Install ArgoCD CLI on Windows

```powershell
$argocdVersion = "v2.12.0"
$out = "$env:USERPROFILE\bin\argocd.exe"
Invoke-WebRequest -Uri "https://github.com/argoproj/argo-cd/releases/download/$argocdVersion/argocd-windows-amd64.exe" -OutFile $out
```

### 15b. Login to ArgoCD via port-forward

```powershell
# Start port-forward in the background
Start-Process powershell -ArgumentList "-Command", "kubectl port-forward svc/argocd-server -n argocd 8080:443"

# Wait a moment for port-forward to be ready
Start-Sleep -Seconds 3

# Get the initial admin password
$password = kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | ForEach-Object { [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_)) }

# Login
argocd login localhost:8080 --username admin --password $password --insecure
```

### 15c. Generate token and store in Secrets Manager

```powershell
$token = argocd account generate-token --account admin

aws secretsmanager update-secret `
  --secret-id intelliops/dev/argocd-api-token `
  --secret-string "{`"token`":`"$token`"}"
```

**⏱ Time:** ~3 minutes
**💰 Cost impact:** $0

---

## Step 16: Configure Slack Callback URL

**🎯 What we're achieving:** Telling Slack where to POST when a user clicks the Approve/Reject buttons on a rollback approval message. Without this, the buttons appear but clicking them does nothing.

1. Back at **https://api.slack.com/apps** → your **IntelliOps** app
2. **Interactivity & Shortcuts** (left sidebar)
3. **Request URL** — paste the URL you saved in Step 12 (the `slack_callback_url` output)
4. Click **Save Changes** at the bottom

Slack immediately does a test POST to verify the URL responds — if the Terraform apply succeeded, this should pass instantly.

**⏱ Time:** ~1 minute
**💰 Cost impact:** $0

---

# Part 7 — Verify Everything Works

## Step 17: Check Cluster Health

**🎯 What we're achieving:** Confirming all workloads are running before attempting a demo. Broken pods here mean the demo will fail in confusing ways.

```powershell
# All apps should be Running
kubectl get pods -n apps-dev
kubectl get pods -n monitoring
kubectl get pods -n logging
kubectl get pods -n kyverno
kubectl get pods -n falco
kubectl get pods -n trivy-system

# All ArgoCD Applications should be Healthy + Synced
kubectl get application -n argocd
```

**Expected:** every pod `Running`, every ArgoCD app `Synced Healthy`.

**⏱ Time:** ~1 minute
**💰 Cost impact:** $0

---

## Step 18: Access the UI

**🎯 What we're achieving:** Confirming the ALB provisioned by the AWS Load Balancer Controller is routing traffic to the UI pod. This is your visual proof that the deployment worked end-to-end.

```powershell
kubectl get ingress -n apps-dev
```

**Expected output:**
```
NAME     CLASS   HOSTS   ADDRESS                                                     PORTS   AGE
ui-dev   alb     *       k8s-appsdev-uidev-abc123-1234567890.us-east-1.elb.amazonaws.com   80      5m
```

Copy the **ADDRESS** and open it in your browser. You should see the IntelliOps UI with panels for creating orders and payments.

**⚠ If `ADDRESS` is empty:** wait 2 more minutes — ALB provisioning is slow. If still empty after 5 minutes, check the AWS Load Balancer Controller logs: `kubectl logs -n kube-system deploy/aws-load-balancer-controller`.

**⏱ Time:** ~2 minutes (mostly waiting for ALB)
**💰 Cost impact:** ALB — ~$0.023/hour (~$17/mo)

---

## Step 19: Access Grafana

**🎯 What we're achieving:** Opening the pre-built IntelliOps dashboard so you can see request rate, error rate, P95 latency, orders created, and payment revenue as the demo unfolds.

```powershell
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80
```

Open **http://localhost:3000** in your browser. Login: `admin` / `admin`.

Navigate to **Dashboards → IntelliOps Services**. Five panels should populate with real metrics from your running pods.

**⏱ Time:** ~1 minute
**💰 Cost impact:** $0 (uses existing pod resources)

---

# Part 8 — Run a Live Demo

## Step 20: Trigger a Chaos Test

**🎯 What we're achieving:** Injecting a controlled failure into the payment service so we can watch the entire anomaly loop react — Prometheus detects the error rate spike, Fluent Bit ships the error logs to CloudWatch, the CloudWatch alarm fires, SNS fans out to the three Lambdas, RCA Lambda calls Claude for narrative, remediator restarts the pod, all with a Slack narrative in real time.

### 20a. Port-forward the payment service

Open a **new PowerShell window** (leave the Grafana port-forward running):

```powershell
kubectl port-forward -n apps-dev svc/payment-service-dev-payment-service 8081:8080
```

### 20b. Inject a 50% error rate for 3 minutes

Open **another PowerShell window**:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8081/admin/inject/errors?rate=0.5&duration=180"
```

**Expected output:**
```
status                      rate duration
------                      ---- --------
error injection active      0.5  180
```

**⏱ Time:** ~10 seconds to trigger
**💰 Cost impact:** $0

---

## Step 21: Watch the AI Response

**🎯 What we're achieving:** Observing the full loop end-to-end. Within ~2 minutes, you'll see everything the AI/remediation layer promises.

### 21a. Watch Grafana

In the Grafana browser tab, the **Error Rate** panel should spike to ~50% within 30 seconds.

### 21b. Watch CloudWatch alarms transition

```powershell
aws cloudwatch describe-alarms `
  --alarm-name-prefix "intelliops-dev-HighErrorRate" `
  --query "MetricAlarms[].[AlarmName,StateValue]" `
  --output table
```

Within ~2 minutes, `intelliops-dev-HighErrorRate-payment-service` transitions from `OK` to `ALARM`.

### 21c. Watch Slack

Two messages appear in your `#intelliops-demos` channel:

**1. RCA narrative** (from RCA Lambda + Claude):
```
🚨 HighErrorRate — payment-service

Incident ID: inc-abc123def456
Detected at: 2026-09-08T14:30:00Z
Metric:      ErrorCount
Model:       bedrock/anthropic.claude-sonnet-4-6-v1:0

**Root cause**: payment-service is emitting 500s at ~50% of request volume,
correlated with the /pay endpoint. Injected fault flag is set via /admin/inject/errors.

**Blast radius**: Payment failures cascade to order confirmation flow.
UI users see failed payments.

**Recommended action**: Restart the payment-service Rollout pods to clear
any accumulated fault-injection state.

**Confidence**: high — direct evidence in logs shows `injected_error` events
at the exact rate.
```

**2. Remediation confirmation** (from Remediator Lambda):
```
✅ restart_rollout — payment-service

Incident:  rem-xyz789
Trigger:   HighErrorRate
Target:    payment-service-dev-payment-service
Time:      2026-09-08T14:30:15Z
```

### 21d. Verify remediation actually happened

```powershell
kubectl get rollout -n apps-dev payment-service-dev-payment-service -o jsonpath='{.spec.restartAt}'
```

Should show a timestamp within the last minute.

### 21e. Check DynamoDB audit

```powershell
aws dynamodb scan `
  --table-name intelliops-dev-incidents `
  --max-items 5 `
  --query "Items[].[incident_id.S, service.S, anomaly_type.S, action_taken.S]" `
  --output table
```

Two rows: one from RCA Lambda (with `rca_summary`), one from Remediator (with `action_taken: restart_rollout`).

**⏱ Time:** 2-3 minutes for the whole loop
**💰 Cost impact:** ~$0.02 (Bedrock invocation + logs + alarm evaluations)

---

## Step 22: Demo the Rollback Approval Flow

**🎯 What we're achieving:** Showing the human-in-the-loop pattern for risky actions. Deployment rollback isn't something you want a Lambda deciding autonomously — the AI narrates the incident, but a human clicks the button.

### 22a. Publish a DeployRegression anomaly

```powershell
$topicArn = (Set-Location infra\envs\dev\lambda; terragrunt output -raw anomalies_topic_arn; Set-Location -)
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

aws sns publish `
  --topic-arn $topicArn `
  --message "{`"service`":`"payment-service`",`"anomaly_type`":`"DeployRegression`",`"timestamp`":`"$timestamp`"}"
```

### 22b. Approve in Slack

An interactive message appears in Slack with two buttons: **✅ Approve rollback** / **❌ Reject**.

Click **Approve rollback**. Behind the scenes:

1. Slack POSTs to your API Gateway URL
2. rollback_execute Lambda verifies the HMAC signature (using the signing secret from Step 6)
3. Lambda queries ArgoCD API for the previous revision
4. Lambda POSTs `/api/v1/applications/payment-service-dev/rollback`
5. The original Slack message updates to `✅ Rollback executed on payment-service-dev (revision N) — approved by @you`

**⚠ Dry-run note:** In the default deploy, the rollback Lambda is not attached to your VPC, so it can't reach the ArgoCD service (which is ClusterIP). You'll see a `🧪 Dry-run rollback recorded` message in Slack. The audit row still lands in DynamoDB. Full rollback works once you attach the Lambda to the VPC — see [construct.md](construct.md) Section "VPC config for rollback Lambda".

**⏱ Time:** ~1 minute
**💰 Cost impact:** ~$0.001 (Lambda + Bedrock)

---

# Part 9 — Teardown

## Step 23: Destroy Everything

**🎯 What we're achieving:** Returning to zero cost. The nuclear teardown removes every AWS resource except the S3 state bucket. Do this at the end of every demo session unless you're actively working with the cluster.

### 23a. Delete ArgoCD Applications first

If you skip this, ArgoCD keeps trying to reconcile against a deleted cluster and Terraform destroy stalls.

```powershell
# From cluster's perspective, delete every ArgoCD-managed app
kubectl delete application --all -n argocd

# Wait for pods to actually go away
kubectl wait --for=delete pods --all -n apps-dev --timeout=120s
kubectl wait --for=delete pods --all -n monitoring --timeout=120s
```

### 23b. Terragrunt destroy (reverse dependency order handled automatically)

```powershell
cd infra\envs\dev
terragrunt run-all destroy
```

Terragrunt walks the dependency graph in reverse. Expected total time: **~15-20 minutes**.

Common hangs (see Appendix A for fixes):
- ALB deletion stuck → delete the load balancer manually via AWS console, then re-run destroy
- ENI cleanup delays → let it retry
- IAM role deletion blocked → EKS worker nodes still terminating, wait

**⏱ Time:** ~20 minutes
**💰 Cost impact:** Stops all recurring charges within a few minutes of destroy starting

---

## Step 24: Confirm Zero Recurring Cost

**🎯 What we're achieving:** Verifying nothing was left behind. AWS bills for orphaned resources you forgot about — always double-check after destroy.

```powershell
# EKS clusters
aws eks list-clusters
# Should return: {"clusters": []}

# EC2 instances
aws ec2 describe-instances --filters "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId"
# Should return: []

# NAT Gateways
aws ec2 describe-nat-gateways --filter "Name=state,Values=available" --query "NatGateways[].NatGatewayId"
# Should return: []

# Load balancers
aws elbv2 describe-load-balancers --query "LoadBalancers[].LoadBalancerName"
# Should return: []

# Kinesis streams
aws kinesis list-streams
# Should return: {"StreamNames": []}
```

If any of these return non-empty results, that resource is still billing. Delete manually via the AWS console or by hand.

**What's left running (all free or pennies/month):**
- S3 state bucket (pennies)
- IAM roles (free)
- OIDC provider (free)
- Bedrock model-access grants (free)
- Secrets Manager entries (~$0.40/mo per secret, delete manually if concerned)

**⏱ Time:** ~2 minutes
**💰 Cost impact:** Confirms $0 recurring going forward

---

# Appendix A — Troubleshooting

**Windows-specific issues:**

| Symptom | Fix |
|---|---|
| `bash: command not found` when Terraform builds Lambda | Reinstall Git for Windows with "Use Git and optional Unix tools from the Command Prompt" option, restart PowerShell |
| `terragrunt: command not found` | Add `$env:USERPROFILE\bin` to your PATH (Step 1c did this temporarily; make it permanent via System Settings → Environment Variables) |
| `pip: command not found` inside Terraform's Lambda build | Reinstall Python via winget with "Add to PATH" option enabled |
| PowerShell won't run scripts ("scripts are disabled") | `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| `Invoke-WebRequest: The remote name could not be resolved` on GitHub URLs | You're behind a corporate proxy. `$env:HTTPS_PROXY = "http://proxy:port"` then retry |

**AWS-specific issues:**

| Symptom | Fix |
|---|---|
| Bedrock returns `AccessDeniedException` | Model access not granted — repeat Step 5. Note: Claude Sonnet 4.6 needs the `us.*` inference-profile ID, e.g. `bedrock/us.anthropic.claude-sonnet-4-6` — not `bedrock/anthropic.claude-sonnet-4-6-v1:0`. Already the default in Terraform. |
| Bedrock returns `RateLimitError: Too many tokens per day` | Free-Tier accounts have a low per-day token quota. Wait for reset (UTC midnight) or switch provider: `$env:TF_VAR_llm_provider = "openai"; cd infra/envs/dev/llm; terragrunt apply` |
| ArgoCD app stuck OutOfSync with `image: :sha` (empty repo) | CI hasn't run yet — either push any commit or manually run the sed command from Step 8 in `construct.md` |
| CloudWatch alarm perpetually `INSUFFICIENT_DATA` | Container Insights add-on needs ~5 minutes after install; for log-based alarms, trigger `/admin/inject/errors` to seed the metric |
| Fluent Bit pods `CrashLoopBackOff` | The bootstrap script's `sed` didn't substitute `ACCOUNT_ID_PLACEHOLDER`. Check with `kubectl -n logging get sa fluent-bit -o yaml` — the role annotation must have your real account ID |
| EKS node group `CREATE_FAILED — not eligible for Free Tier` | Free-Tier-restricted account. Both nodegroups are `t3.small` by default (eligible). Do not raise to `t3.medium`. |
| Kinesis apply fails with `SubscriptionRequiredException` | Expected on Free-Tier/new accounts. The `kinesis` module is `skip = true` by default; nothing downstream consumes it. |
| Pods stuck Pending with `Too many pods` | vpc-cni prefix delegation raises max-pods to ~110 on t3.small. If a node still reports max-pods=8, it was created before the NodeConfig landed — recycle it with `aws eks update-nodegroup-version --cluster-name intelliops-dev --nodegroup-name <ng> --force` |
| RCA Lambda cold-starts with `No module named 'pydantic_core._pydantic_core'` | `lambda/build_function.py` must pass `--platform manylinux2014_x86_64 --python-version 3.12 --only-binary=:all:` to pip. Already fixed on `main`. |
| CI Docker build: `invalid tag "***.dkr.ecr..."` | The `AWS_ACCOUNT_ID` GitHub secret has a trailing newline. Reset with `"573978149165" \| gh secret set AWS_ACCOUNT_ID --no-store` (or use `printf %s` on bash). |
| CI OIDC assume-role: `AccessDenied ... sts:AssumeRoleWithWebIdentity` | GitHub's post-2025 OIDC subject includes immutable IDs (`repo:{owner}@{ownerId}/{repo}@{repoId}:...`). The Terraform `github_actions` module writes a trust policy that matches this; roll-your-own roles must too. |
| CD workflow: `error: You must be logged in to the server` at kubectl step | The GitHub Actions role has no EKS Access Entry. Fixed by the Terraform `github_actions` module (creates entry + associates `AmazonEKSClusterAdminPolicy`). |
| CD workflow hangs at `until curl ... /healthz` | `argocd-initial-admin-secret` doesn't exist (ArgoCD v3 dropped auto-creation). Fixed in `bootstrap.sh` / `bootstrap.ps1` — they seed both the secret and the bcrypt hash. |
| CI Trivy container scan blocks on `perl-base` CRITICALs | Soft-gated for now (`continue-on-error: true`). Restore the hard gate after moving app Dockerfiles to distroless / Alpine. |
| `terragrunt destroy` hangs on VPC | Load balancer, NAT gateway, or ENI still in use. Delete via console, then retry |

---

# Appendix B — Cost Optimisation

**Rules of thumb:**

- **Never leave the cluster running overnight** unless you're actively working with it. $250/month adds up fast.
- **Bedrock is cheaper than you think** — a typical RCA is 1500 input + 500 output tokens ≈ $0.008 per invocation. You'd need to fire hundreds of alarms per day for Bedrock to be a meaningful cost.
- **NAT Gateway is your biggest hidden cost** ($32/mo before any data transfer). If you're doing an extended session, consider adding VPC Endpoints for ECR, S3, STS, Secrets Manager to route traffic without going through NAT.

**Aggressive teardowns:**

```powershell
# Scale system nodes to 1 (saves ~$30/mo, breaks HA)
aws eks update-nodegroup-config `
  --cluster-name intelliops-dev `
  --nodegroup-name system `
  --scaling-config minSize=1,maxSize=2,desiredSize=1

# Delete workload nodes entirely (Karpenter recreates on pending pods)
aws eks delete-nodegroup --cluster-name intelliops-dev --nodegroup-name workload
```

---

# Appendix C — What Each Component Does

Quick reference of the moving parts you provisioned:

| Component | Purpose | Cost |
|---|---|---|
| VPC + Subnets | Network isolation, 3-AZ layout | Free |
| NAT Gateway | Private-subnet pods reaching the internet | $32/mo |
| EKS Control Plane | Managed Kubernetes API server | $73/mo |
| System Nodes (t3.small × 1) | Karpenter (single replica, memory-tuned), coredns, kube-proxy, vpc-cni, ebs-csi | ~$15/mo |
| Workload Nodes (t3.small × 3) | ArgoCD, Rollouts, Fluent Bit, security add-ons, apps | ~$45/mo |
| Karpenter | Provisions extra workload nodes when pending pods appear | Free (nodes cost extra) |
| ECR Repositories | Docker image storage | Free tier |
| ALB | External HTTP entry point for the UI | ~$17/mo |
| CloudWatch Log Group | Structured JSON app logs, 30-day retention | ~$5/mo |
| ~~Kinesis Streams~~ | Skipped — Free-Tier-restricted accounts reject `CreateStream`; not consumed downstream | $0 |
| DynamoDB (on-demand) | Incident audit trail | Pennies |
| Secrets Manager (×5) | LLM keys, Slack webhook, ArgoCD token, signing secret | ~$2/mo |
| Lambda × 4 | RCA + remediator + rollback request + rollback execute | Pennies |
| API Gateway HTTP API | Slack callback endpoint | Pennies |
| SNS Topic | Anomaly fan-out | Pennies |
| CloudWatch Alarms × 6 | HighCPU, MemoryPressure, HighErrorRate per service | Pennies |
| Container Insights | Pod-level CPU/memory metrics | ~$3/mo |
| Bedrock | LLM inference for RCA | Pennies per invocation |

---

## What you achieved

- Provisioned a production-grade EKS platform with GitOps, canary deploys, and progressive delivery
- Wired a multi-LLM AI observability layer that generates human-readable RCA narratives from real anomalies
- Set up autonomous remediation for safe actions and human-approved rollback for risky ones
- Enabled defence-in-depth security: Kyverno admission control, Falco runtime detection, Trivy operator scanning, network policies, and external secrets
- Demonstrated the full loop live: fault injection → alarm → SNS → Claude RCA → auto-remediation → Slack narrative → DynamoDB audit
- Kept it under $2 by tearing down when done

You now have a live-demoable portfolio project that spans SRE, MLOps, and Platform Engineering competencies.
