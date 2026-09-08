# Construct — Step-by-Step AWS Build with Minimal Cost

A walkthrough for provisioning the full IntelliOps stack on AWS, running one end-to-end demo, and tearing it back down to **zero recurring cost**.

**Time to first working demo:** ~40 minutes
**Cost per demo session (~2 hours):** **~$1.50**
**Cost if left running 24/7:** ~$250/month

---

## Contents

1. [Cost model — read this first](#1-cost-model-read-this-first)
2. [Prerequisites](#2-prerequisites)
3. [One-time setup](#3-one-time-setup)
4. [Environment variables](#4-environment-variables)
5. [Provision infrastructure](#5-provision-infrastructure)
6. [Bootstrap ArgoCD](#6-bootstrap-argocd)
7. [Verify the deployment](#7-verify-the-deployment)
8. [Run a live demo](#8-run-a-live-demo)
9. [Teardown to zero cost](#9-teardown-to-zero-cost)
10. [Cost minimisation tips](#10-cost-minimisation-tips)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Cost model — read this first

The unavoidable baseline while the cluster exists is roughly:

| Component | Per hour | Per day | Per month |
|---|---|---|---|
| EKS control plane | $0.10 | $2.40 | $73 |
| NAT Gateway | $0.045 + traffic | ~$1.10 | ~$32 |
| 2× t3.medium system nodes | $0.083 | $2.00 | ~$60 |
| **Baseline total** | **~$0.23/hr** | **~$5.50/day** | **~$165/mo** |

Everything else (Kinesis, Lambda, Bedrock invocations, DynamoDB on-demand, CloudWatch, Secrets Manager) is either pay-per-use pennies or ≤$25/mo.

### The strategy: run in bursts, tear down between

Build the stack when you want to demo, work with it for ~2 hours, tear it down. That's roughly **$1.50 per demo session** vs. $250/month running continuously.

Everything except the S3 state bucket is destroyed by `terragrunt run-all destroy` — the bucket itself stores tens of KB and costs pennies to keep forever.

---

## 2. Prerequisites

**Tools on your machine:**

```bash
aws --version              # >= 2.15
terraform --version        # >= 1.5
terragrunt --version       # >= 0.55
kubectl version --client   # >= 1.28
helm version               # >= 3.14
gh --version               # >= 2.40  (optional, only if you'll use gh CLI)
python --version           # >= 3.12  (Terraform builds Lambda zips with pip)
```

**AWS account & credentials:**

- AWS account with permission to provision VPC, EKS, IAM, Kinesis, DynamoDB, Lambda, Secrets Manager, ECR, CloudWatch, API Gateway, SNS
- `aws configure` set up, or `AWS_PROFILE` exported

**Slack app** (one-time, ~5 minutes):

- Create at https://api.slack.com/apps → From scratch
- Enable **Incoming Webhooks** → add to your target channel → copy the webhook URL
- Enable **Interactivity & Shortcuts** — you'll paste the API Gateway URL here after Terraform apply
- Grab the **Signing Secret** from Basic Information → App Credentials

**LLM credentials — only if not using Bedrock:**

- Bedrock is the default and uses IAM automatically — **no API key needed**. Recommended.
- OpenAI: get an API key at https://platform.openai.com/api-keys
- Gemini: get one at https://aistudio.google.com/apikey

---

## 3. One-time setup

### 3a. Create the Terraform state bucket

```bash
export AWS_REGION=us-east-1
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws s3api create-bucket \
  --bucket intelliops-tfstate-dev \
  --region $AWS_REGION

aws s3api put-bucket-versioning \
  --bucket intelliops-tfstate-dev \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket intelliops-tfstate-dev \
  --server-side-encryption-configuration '{
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
  }'
```

### 3b. Create the GitHub Actions OIDC role  (skip if you won't push from CI)

If you'll only demo locally without pushing changes back, this can be skipped. Otherwise the CI/CD workflows need an OIDC-assumable role.

```bash
# One-time: create the OIDC provider for GitHub Actions
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# Create the role — replace <YOUR_GITHUB_USER>/<REPO_NAME>
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:mrsrujan/IntelliOps:*"
      }
    }
  }]
}
EOF

aws iam create-role \
  --role-name intelliops-github-actions \
  --assume-role-policy-document file://trust-policy.json

aws iam attach-role-policy \
  --role-name intelliops-github-actions \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess   # broad for demo; scope down for real use
```

Add these as GitHub repo secrets (Settings → Secrets and variables → Actions):
- `AWS_ACCOUNT_ID` — your account ID
- `AWS_GITHUB_ACTIONS_ROLE` — `arn:aws:iam::${ACCOUNT_ID}:role/intelliops-github-actions`

---

## 4. Environment variables

Set these before every apply. Consider putting them in a `.envrc` (with `direnv`) or a shell script — **never commit them**.

```bash
# Terraform will use these via TF_VAR_* env vars
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."   # from Slack app
export TF_VAR_slack_signing_secret="abc123..."                     # from Slack app
export TF_VAR_argocd_api_token=""                                   # empty for now, fill after ArgoCD is up

# LLM provider (default is bedrock — no API key needed)
export TF_VAR_llm_provider="bedrock"
export TF_VAR_llm_model="bedrock/anthropic.claude-sonnet-4-6-v1:0"

# If you're using OpenAI instead:
# export TF_VAR_llm_provider="openai"
# export TF_VAR_llm_model="openai/gpt-4o"
# export TF_VAR_openai_api_key="sk-..."

# If you're using Gemini:
# export TF_VAR_llm_provider="gemini"
# export TF_VAR_llm_model="gemini/gemini-2.0-pro"
# export TF_VAR_gemini_api_key="AIza..."
```

For Bedrock: make sure you've **requested model access** for Claude Sonnet 4.6 in the Bedrock console (Bedrock → Model access). This takes ~1 minute of approval time.

---

## 5. Provision infrastructure

```bash
cd infra/envs/dev
terragrunt run-all apply
```

Terragrunt walks the module dependency graph and applies each unit in order. Expected timing:

| Unit | Time |
|---|---|
| vpc | ~3 min |
| ecr | ~10 sec |
| eks (biggest) | ~15-20 min |
| logs · kinesis · dynamodb · llm | ~1 min each (parallel) |
| lambda | ~2 min (pip install runs during archive) |
| observability | ~1 min |
| remediation | ~2 min |
| **Total** | **~25 min** |

If you'd rather see each step:

```bash
cd infra/envs/dev/vpc  && terragrunt apply
cd ../ecr              && terragrunt apply
cd ../eks              && terragrunt apply
cd ../logs             && terragrunt apply
cd ../kinesis          && terragrunt apply
cd ../dynamodb         && terragrunt apply
cd ../llm              && terragrunt apply
cd ../lambda           && terragrunt apply
cd ../observability    && terragrunt apply
cd ../remediation      && terragrunt apply
```

Grab the Slack callback URL from the remediation output:

```bash
cd infra/envs/dev/remediation
terragrunt output slack_callback_url
```

Paste it into your Slack app's **Interactivity → Request URL**.

---

## 6. Bootstrap ArgoCD

Connect kubectl and install ArgoCD + Argo Rollouts:

```bash
aws eks update-kubeconfig --name intelliops-dev --region us-east-1

bash k8s/argocd/install/bootstrap.sh
```

The script:
- Installs ArgoCD v2.12.0 + Argo Rollouts v1.7.2
- Substitutes `ACCOUNT_ID_PLACEHOLDER` in every ArgoCD app manifest with your real account ID
- Applies the ArgoCD Project and all Applications

Wait for ArgoCD to sync everything (~5 min):

```bash
kubectl -n argocd wait --for=condition=available --timeout=300s deploy/argocd-server
argocd login localhost:8080 --username admin \
  --password $(kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d) \
  --insecure
argocd app list
argocd app wait -l argocd.argoproj.io/instance --health --timeout 600
```

Generate an ArgoCD API token so the rollback Lambda can talk back:

```bash
argocd account generate-token --account admin
```

Update the Secrets Manager entry:

```bash
aws secretsmanager update-secret \
  --secret-id intelliops/dev/argocd-api-token \
  --secret-string "{\"token\":\"$(argocd account generate-token --account admin)\"}"
```

---

## 7. Verify the deployment

```bash
# Apps running
kubectl get pods -n apps-dev

# ALB URL
kubectl get ingress -n apps-dev
# Open the ADDRESS field — the IntelliOps UI loads

# Grafana
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80
# open http://localhost:3000  (admin / admin) — dashboard "IntelliOps Services" is preloaded

# CloudWatch alarms provisioned
aws cloudwatch describe-alarms --alarm-name-prefix "intelliops-dev-"

# CloudWatch logs coming in
aws logs tail /eks/intelliops-dev/apps --since 5m --follow
```

---

## 8. Run a live demo

Trigger the whole chain: chaos → alarm → SNS → RCA → Slack.

### Option A — Chaos GitHub Actions workflow (recommended)

1. GitHub → Actions → **Chaos** → Run workflow
2. Pick: `service=payment-service`, `fault=errors`, `intensity=0.5`, `duration_seconds=180`
3. Within ~2 minutes:
   - Grafana Error Rate panel spikes to ~50%
   - CloudWatch alarm `intelliops-dev-HighErrorRate-payment-service` transitions to ALARM
   - Slack gets an incident summary with Claude's RCA narrative
   - Slack gets an auto-remediation confirmation: "🔁 restart_rollout on payment-service"
   - `kubectl get rollout -n apps-dev payment-service-dev-payment-service` shows a fresh restart

### Option B — Direct SNS publish (no GitHub Actions needed)

```bash
TOPIC=$(cd infra/envs/dev/lambda && terragrunt output -raw anomalies_topic_arn)

aws sns publish --topic-arn $TOPIC --message '{
  "service":"payment-service","anomaly_type":"HighCPU",
  "metric":"cpu_pct","value":92,"threshold":80,
  "timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
}'
```

### Rollback approval demo

```bash
aws sns publish --topic-arn $TOPIC --message '{
  "service":"payment-service","anomaly_type":"DeployRegression",
  "timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
}'
```

Slack posts an interactive message. Click **Approve rollback** → API Gateway → HMAC-verified Lambda → ArgoCD rollback (or dry-run audit if VPC config not in place).

---

## 9. Teardown to zero cost

The nuclear option — everything except the S3 state bucket:

```bash
# 1. Destroy everything ArgoCD manages
argocd app delete -l argocd.argoproj.io/instance --cascade --yes || true
kubectl delete application --all -n argocd

# 2. Then Terraform
cd infra/envs/dev
terragrunt run-all destroy
```

Expected: **~15 minutes** to fully drain. `run-all destroy` handles dependency order in reverse.

If teardown gets stuck on ENIs, load balancers, or IAM roles (common with EKS):

```bash
# Manual ALB cleanup
aws elbv2 describe-load-balancers | jq '.LoadBalancers[].LoadBalancerArn'
aws elbv2 delete-load-balancer --load-balancer-arn <arn>

# Manual security group / ENI cleanup usually needed if ALB deletion was skipped
aws ec2 describe-security-groups --filters "Name=tag:aws:eks:cluster-name,Values=intelliops-dev"
```

After teardown, only these should remain:
- S3 state bucket (pennies/month)
- IAM roles (free)
- OIDC provider (free)
- Bedrock model access grants (free)

---

## 10. Cost minimisation tips

**During a demo session:**
- Nothing to do — the defaults are already spot-preferred for workload nodes.

**If you need the cluster for longer than a demo:**
- Scale system node group to 1: `aws eks update-nodegroup-config --cluster-name intelliops-dev --nodegroup-name system --scaling-config minSize=1,maxSize=2,desiredSize=1`  → saves ~$30/mo
- Delete NAT Gateway when not actively using outbound (breaks all outbound: metric-shipping, Bedrock API, ECR pulls from private subnets). Recreate with `terragrunt apply` when needed. Saves ~$32/mo.
- Use `single_nat_gateway = true` — already the default in the dev env.

**Only pay for what fires:**
- Kinesis: switch to `ON_DEMAND` in `infra/modules/kinesis/main.tf` if event volume is bursty. Pay per PUT rather than per shard-hour. Slightly higher per-event, but $0 idle.
- Bedrock: pay per token, no reservation. A typical RCA prompt is ~1,500 tokens in + 500 out = ~$0.008 per invocation.
- Lambda + DynamoDB (on-demand) + SNS + API Gateway HTTP API: effectively free at demo volume.

**What you cannot make cheaper:**
- EKS control plane is a fixed $73/mo while the cluster exists.
- NAT Gateway is $32/mo minimum. VPC endpoints for ECR + S3 + STS + Secrets Manager + Logs would eliminate most NAT traffic charges, but the NAT itself still needs to exist for anything else.

---

## 11. Troubleshooting

**`terraform apply` on eks module says "cluster creator has no permissions"**
The IAM identity that ran the apply becomes cluster admin via `enable_cluster_creator_admin_permissions = true`. If you switch identities mid-flight, you'll lose access. Re-run apply as the original identity, or add yourself as an Access Entry.

**ArgoCD app stuck "OutOfSync" — image tag mismatch**
CI hasn't run yet, so `helm/<service>/values.yaml` still has `repository: ""`. Either:
- Push any commit to `main` (CI will populate the values), or
- Manually set: `sed -i "s|repository:.*|repository: \"$ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/intelliops/order-service\"|" helm/order-service/values.yaml` and commit.

**Bedrock returns AccessDeniedException**
You haven't requested access to Claude Sonnet 4.6 in the Bedrock console. Bedrock → Model access → Manage model access → check Anthropic Claude models → Save.

**Fluent Bit pods CrashLoopBackOff**
The `ACCOUNT_ID_PLACEHOLDER` sed step in bootstrap.sh didn't run. Verify:
```bash
kubectl -n logging get sa fluent-bit -o yaml | grep role-arn
# Should show the real account, not "ACCOUNT_ID_PLACEHOLDER"
```
Rerun `bash k8s/argocd/install/bootstrap.sh` or manually patch the ServiceAccount annotation.

**CloudWatch alarms in INSUFFICIENT_DATA forever**
Container Insights add-on needs ~5 minutes after install to start reporting metrics. Log-based ErrorCount alarms need at least one WARN/ERROR log in the window. Trigger `/admin/inject/errors` to seed the metric.

**Chaos GitHub Actions can't reach the pod**
The chaos workflow runs `kubectl port-forward`, which requires the runner to have EKS access. Confirm `AWS_GITHUB_ACTIONS_ROLE` has permission on the cluster (via aws-auth ConfigMap or Access Entry).

**Rollback Lambda posts dry-run audit instead of actually rolling back**
Expected until VPC config is added to the rollback_execute Lambda so it can reach ArgoCD's ClusterIP service. See [design note in README](README.md#not-included-by-design).

---

Once you're comfortable with the flow, the whole cycle is:

```bash
# Start a demo session
cd infra/envs/dev && terragrunt run-all apply     # ~25 min, ~$0.25 spent
bash k8s/argocd/install/bootstrap.sh              # ~5 min
# ... run demos, do work ...

# End the session
terragrunt run-all destroy                        # ~15 min, back to $0
```

Roughly $1.50 per 2-hour session. Perfect for portfolio walk-throughs during interviews.
