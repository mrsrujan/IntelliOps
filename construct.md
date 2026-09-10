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

### 3b. Register the GitHub Actions OIDC provider  (skip if you won't push from CI)

If you'll only demo locally without pushing changes back, this whole section can be skipped. Otherwise the CI/CD workflows need an OIDC-assumable role.

The **IAM role, trust policy, and EKS access entry are now created by the Terraform `github_actions` module** — you don't have to author them by hand. Only the account-wide OIDC provider itself is a one-time manual step:

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

(If it already exists you'll get `EntityAlreadyExists` — safe to ignore.)

If your GitHub repository isn't `mrsrujan/IntelliOps`, override the module default in step 5 with `-var github_repository=<owner>/<name>` or by exporting `TF_VAR_github_repository`.

After Step 5 finishes, plug the module outputs into your repo secrets:

```bash
cd infra/envs/dev/github_actions
ROLE_ARN=$(terragrunt output -raw role_arn)
gh secret set AWS_GITHUB_ACTIONS_ROLE --repo <owner>/<repo> --body "$ROLE_ARN"
printf %s "$ACCOUNT_ID" | gh secret set AWS_ACCOUNT_ID --repo <owner>/<repo>
```

*(`printf %s` is important — a trailing newline in the account-id secret breaks Docker's `tag` reference format on CI.)*

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
# Anthropic Claude Sonnet 4.6 on Bedrock only serves via a US inference
# profile (on-demand throughput is not available on the raw foundation
# model). Do not use the older `-v1:0` suffix.
export TF_VAR_llm_model="bedrock/us.anthropic.claude-sonnet-4-6"

# If you're using OpenAI instead:
# export TF_VAR_llm_provider="openai"
# export TF_VAR_llm_model="openai/gpt-4o"
# export TF_VAR_openai_api_key="sk-..."

# If you're using Gemini:
# export TF_VAR_llm_provider="gemini"
# export TF_VAR_llm_model="gemini/gemini-2.0-pro"
# export TF_VAR_gemini_api_key="AIza..."
```

For Bedrock: AWS retired the "Manage model access" page in 2025. Serverless foundation models are now enabled by default in commercial regions, but Anthropic models require a **one-time usage form** — open the Bedrock console at https://console.aws.amazon.com/bedrock/, go to the Chat playground, pick Claude Sonnet 4.6, and fill in the form if prompted. Approval is instant for personal accounts.

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
cd infra/envs/dev/vpc              && terragrunt apply
cd ../ecr                          && terragrunt apply
cd ../eks                          && terragrunt apply   # ~15-20 min
cd ../logs                         && terragrunt apply
cd ../dynamodb                     && terragrunt apply
cd ../llm                          && terragrunt apply
cd ../lambda                       && terragrunt apply
cd ../observability                && terragrunt apply
cd ../remediation                  && terragrunt apply
cd ../github_actions               && terragrunt apply   # only if you'll use CI
# kinesis module is marked skip=true — the reference architecture doesn't
# consume its outputs, and some AWS accounts (Free-Tier restricted, new
# personal accounts) return SubscriptionRequiredException for it.
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
- Installs ArgoCD v3.0.0 + Argo Rollouts v1.8.0
- Seeds `argocd-initial-admin-secret` and patches the bcrypt hash in `argocd-secret` (ArgoCD v3 no longer creates the initial-admin secret automatically)
- Registers the built-in `in-cluster` destination secret so the ApplicationSet can resolve `https://kubernetes.default.svc` (also no longer implicit in v3)
- Substitutes `ACCOUNT_ID_PLACEHOLDER` in every ArgoCD app manifest with your real account ID
- Applies the ArgoCD Project and all Applications

On Windows, use `pwsh k8s/argocd/install/bootstrap.ps1` instead — same behaviour.

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
You haven't completed the one-time Anthropic usage form. Open the Bedrock console → Chat playground → pick a Claude model → submit the use-case form when prompted. Access is instant for personal accounts. (AWS retired the old "Manage model access" page in 2025 — the playground flow is now the canonical way in.)

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

**EKS node group CREATE_FAILED — `not eligible for Free Tier`**
Some AWS personal accounts are pinned to Free-Tier-eligible instance types. The default (`t3.small` on both nodegroups) is eligible; do not raise to `t3.medium` on such accounts. The workload nodegroup is intentionally `desired_size = 3` because prefix delegation + max-pods=110 is per-node — a single t3.small cannot fit ArgoCD, Prometheus, Falco, and the apps together on its own even with the raised pod cap.

**`Runtime.ImportModuleError: No module named 'pydantic_core._pydantic_core'` in the RCA Lambda**
Fixed on `main` — `lambda/build_function.py` uses `--platform manylinux2014_x86_64 --python-version 3.12 --implementation cp --only-binary=:all:` when pip-installing Lambda dependencies. If you see this on a fork/branch that predates the fix, cherry-pick that change.

**CI push-back fails with `AccessDenied ... sts:AssumeRoleWithWebIdentity`**
GitHub Actions' post-2025 OIDC token uses immutable identifiers — the `sub` claim is `repo:{owner}@{ownerId}/{repo}@{repoId}:...`. The Terraform `github_actions` module already writes a trust policy that matches this via the stable `repository` claim + a `sub` StringLike with `@*` in both slots. If you rolled your own role, replicate that pattern.

**CI Docker build fails with `invalid tag "***.dkr.ecr..."` / `invalid reference format`**
The `AWS_ACCOUNT_ID` GitHub secret has a trailing newline. Reset with `printf %s "$ACCOUNT_ID" | gh secret set AWS_ACCOUNT_ID` — `echo` will re-add the newline.

**Pods stuck Pending with `Too many pods` on t3.small nodes**
The vpc-cni prefix-delegation addon config (`ENABLE_PREFIX_DELEGATION=true`) plus the `cloudinit_pre_nodeadm` NodeConfig on each managed nodegroup together raise max-pods from 8 to ~110. Both are already in `infra/modules/eks/main.tf`. If you see max-pods=8 on a Ready node, the nodegroup was created before the NodeConfig landed — recycle it: `aws eks update-nodegroup-version --cluster-name intelliops-dev --nodegroup-name <ng> --force`.

**CD workflow times out at `until curl ... localhost:8080/healthz`**
`kubectl port-forward` silently failed. Two common causes: (a) the GitHub Actions role has no EKS Access Entry (fixed by the `github_actions` Terraform module — check `aws eks list-access-entries --cluster-name intelliops-dev`), or (b) the `argocd-initial-admin-secret` doesn't exist (fixed by the updated bootstrap script — check `kubectl -n argocd get secret argocd-initial-admin-secret`).

**Trivy container scan blocks the pipeline on `perl-base` CRITICALs**
The scan is currently soft-gated (`continue-on-error: true`, `exit-code: "0"`) because the python base image ships `fix_deferred` perl CVEs we can't patch here. Restore the hard gate once the app Dockerfiles are moved to a distroless or Alpine base.

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
