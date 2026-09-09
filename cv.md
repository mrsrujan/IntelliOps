# IntelliOps — CV / Resume Entries

Copy-paste sections below into your CV, LinkedIn, or portfolio site. Pick the length that matches your target format.

---

## One-line elevator pitch

> Self-healing AWS EKS platform where LLMs (Claude / GPT-4o / Gemini) analyze production anomalies and Lambda-driven remediation acts on them autonomously.

---

## Short version — 2 lines (fits under a job or in a "Notable Projects" side-bar)

**IntelliOps** — *AI-Powered Cloud-Native Observability & Auto-Remediation Platform*
Built an end-to-end AWS EKS platform with GitOps canary delivery, multi-LLM root-cause analysis (Bedrock / OpenAI / Gemini via LiteLLM), and Lambda-driven autonomous remediation. 10 Terragrunt modules, 4 Lambda functions, 5-gate DevSecOps CI, defence-in-depth security (Kyverno, Falco, Trivy, ESO, NetworkPolicies).

---

## Standard CV version — 5-6 bullets (for most tech resumes)

### IntelliOps — AI-Powered EKS Observability & Auto-Remediation Platform · [github.com/mrsrujan/IntelliOps](https://github.com/mrsrujan/IntelliOps)

*Personal project · 2026 · AWS, Kubernetes, Terraform, Python, LiteLLM*

- Designed a **self-healing platform** on Amazon EKS 1.33 that uses LLMs to analyze production anomalies and autonomously remediates them — from `git push` to canary deploy to anomaly → RCA → remediation, all in under 3 minutes
- Built a **provider-agnostic AI layer** with LiteLLM: a single Terraform variable switches the RCA Lambda between **Amazon Bedrock (Claude Sonnet 4.6)**, **OpenAI GPT-4o**, or **Google Gemini 2.0** — same code path, no provider lock-in
- Implemented **tiered autonomous remediation** via 4 Lambdas: safe actions (scale, restart, cordon) execute automatically through the EKS API using IRSA + Access Entries; risky rollbacks require **Slack-approved, HMAC-verified callback** through API Gateway
- Shipped a **production-grade CI/CD pipeline**: GitHub Actions → ArgoCD → **Argo Rollouts canary (20 % → 50 % → 100 %)**, with 5-gate DevSecOps (Gitleaks hard, Trivy image hard, pip-audit / Bandit / Trivy IaC soft)
- Delivered **defence-in-depth security**: Kyverno admission policies, Falco runtime threat detection (eBPF), Trivy Operator continuous scanning, External Secrets Operator, default-deny NetworkPolicies
- Wrote **~3 500 lines of infrastructure code** across 10 modular Terragrunt units (VPC, EKS, ECR, Kinesis, DynamoDB, Lambda, API Gateway, Secrets Manager, IRSA, CloudWatch); full teardown returns cost to $0

---

## Extended portfolio version (for portfolio site, LinkedIn description, cover letter)

### IntelliOps

**AI-Powered Cloud-Native Observability & Auto-Remediation Platform**
*Personal project · Sept 2026 · [github.com/mrsrujan/IntelliOps](https://github.com/mrsrujan/IntelliOps)*

An end-to-end reference architecture that turns a plain EKS cluster into a self-healing platform. When something goes wrong in production, CloudWatch alarms fan out to three Lambda subscribers: one calls a Large Language Model to generate a human-readable root-cause narrative (Bedrock Claude by default, OpenAI or Gemini switchable via one Terraform variable), one auto-remediates safe categories through the Kubernetes API, and one posts a Slack approval message for actions that need a human — like deployment rollback.

The project spans SRE, MLOps, and Platform Engineering competencies in one cohesive story:

- **Infrastructure**: Terraform + Terragrunt across 10 per-module units. Amazon EKS 1.33 with Karpenter v1 (spot + on-demand), AWS Load Balancer Controller, IRSA for every workload
- **CI/CD**: GitHub Actions builds, scans, and pushes images; commits the new image tag back to Git; ArgoCD's ApplicationSet detects the change; Argo Rollouts performs a 20 % → pause → 50 % → pause → 100 % canary. GitOps is the single source of truth — no drift possible.
- **DevSecOps**: 5-gate CI pipeline. Gitleaks blocks on any secret detection. Trivy blocks on CRITICAL image CVEs. pip-audit, Bandit, and Trivy IaC scans report as soft gates so the pipeline doesn't jam on nuisance findings.
- **Observability**: Structured JSON logging with `X-Request-ID` propagation end-to-end, Fluent Bit shipping to CloudWatch, kube-prometheus-stack in-cluster, Grafana dashboards as ConfigMaps, CloudWatch Container Insights + Application Signals
- **AI / ML**: LiteLLM abstraction over three LLM providers, structured Claude prompts with CloudWatch Logs Insights context + DynamoDB similar-incidents lookup, SageMaker LSTM notebook included as a demonstrable ML artifact (runtime uses managed CloudWatch anomaly detection to avoid a $72/mo endpoint)
- **Auto-remediation**: EKS API access from Lambda via IRSA + Access Entries + STS-signed presigned URLs (no `eks-token` dependency); actions include scaling Argo Rollouts, restarting deployments, cordoning nodes. HMAC-verified Slack callback for rollback approval, with 5-minute replay window.
- **Security**: Runtime layer of Kyverno admission control (5 baseline ClusterPolicies), Falco DaemonSet with eBPF probes, Trivy Operator continuous scanning, External Secrets Operator with AWS Secrets Manager ClusterSecretStore, comprehensive default-deny NetworkPolicies with explicit allow paths

Every layer is deployable via one `terragrunt run-all apply` (~25 min) and destroyable via one `terragrunt run-all destroy` (~15 min). A GitHub Actions "chaos" workflow triggers fault injection endpoints on the running services so the whole detect → analyse → remediate loop can be demoed end-to-end in under 3 minutes.

---

## Tech Stack (ATS-friendly keyword block)

```
Cloud:           AWS, Amazon EKS, ECR, ALB, Lambda, SNS, DynamoDB, Kinesis, Secrets Manager,
                 CloudWatch (Alarms, Logs Insights, Container Insights, Application Signals),
                 API Gateway, S3, Amazon Bedrock
IaC:             Terraform 1.5+, Terragrunt, HCL, AWS Provider v6
Kubernetes:      Kubernetes 1.33, Karpenter v1, AWS Load Balancer Controller, IRSA, Access Entries
GitOps:          Argo CD 3.0, ArgoCD ApplicationSet, Argo Rollouts 1.8 (canary)
CI/CD:           GitHub Actions, OIDC federation, Docker, ECR
Observability:   Prometheus, Grafana, kube-prometheus-stack, Fluent Bit, structured JSON logging
AI / ML:         LiteLLM, Amazon Bedrock (Claude Sonnet 4.6), OpenAI (GPT-4o),
                 Google Gemini 2.0, Amazon SageMaker, PyTorch (LSTM)
DevSecOps:       Gitleaks, Trivy (image + IaC), pip-audit, Bandit, SBOM
Runtime Sec:     Kyverno (admission), Falco (eBPF runtime detection), Trivy Operator,
                 External Secrets Operator, NetworkPolicies
Languages:       Python 3.12 (FastAPI, pytest), Bash, PowerShell
Automation:      Slack Bolt / interactive callbacks, HMAC signature verification
```

---

## What makes it different from a "regular" DevOps portfolio project

Recruiters see a lot of "I built a Kubernetes cluster with GitOps" projects. Here's what specifically differentiates this one — worth referencing verbatim in cover letters or interview intros:

1. **AI is integrated, not bolted on.** Most portfolio projects that mention AI either wrap an LLM around a chat interface, or install a pre-built RAG stack. This project uses the LLM as an *operational* component — Claude reads live production logs, cross-references past incidents, and generates structured RCA that a human can act on. The LLM is one node in a real event-driven pipeline, not a demo.

2. **Provider-agnostic LLM by design, not by accident.** Multi-LLM support via LiteLLM is a deploy-time flag. Switching Bedrock → OpenAI → Gemini is one Terraform variable — same Lambda code path via LiteLLM abstraction, same prompts, no vendor lock-in. Interviewers immediately recognise this as production-mature thinking.

3. **Autonomous remediation with tiered safety.** Two-Lambda pattern separates *safe* actions (scale, restart, cordon — auto-execute) from *risky* actions (deployment rollback — Slack approval flow via HMAC-verified API Gateway callback). This mirrors how mature SRE teams actually architect self-healing systems.

4. **Real infrastructure discipline.** 10 modular Terragrunt units with proper dependency ordering, mock outputs for `plan` phases, and account-ID substitution at bootstrap so no secrets leak into git. Not a mono-`.tf` file.

5. **Cost-conscious architecture decisions, documented.** SageMaker LSTM notebook included as a demonstrable ML artifact, but the runtime path uses CloudWatch managed anomaly detection to avoid a $72/mo SageMaker endpoint. Shows "right tool for the job" over-engineering avoidance — and I documented *why* that trade-off was made.

6. **End-to-end demoable in under 3 minutes.** GitHub Actions chaos workflow → error rate spike → CloudWatch alarm → SNS fanout → Claude RCA to Slack → auto-remediation confirmation → DynamoDB audit row. Live, on real infrastructure, in front of an interviewer.

7. **Full teardown returns cost to $0.** Every AWS resource except the state bucket is destroyed by one command. Docs quote actual demo-session cost (~$1.50) versus running-24/7 cost (~$250/mo). Shows I know what I'm actually spending, not just what I'm building.

---

## Numbers worth citing

Use these if your CV format encourages metrics:

- **16 commits** telling a real engineering story (Phase 1 through Phase 6 + docs + fixes discovered during real deployment)
- **10 Terragrunt modules · ~3,500 lines of HCL** across VPC, EKS, ECR, Kinesis, DynamoDB, Lambda, API Gateway, Secrets Manager, IRSA, CloudWatch
- **4 Lambda functions** (~1,200 lines of Python)
- **3 microservices** with structured logging + request-ID propagation + fault-injection endpoints
- **5-gate DevSecOps pipeline** (Gitleaks + Trivy image + Trivy IaC + pip-audit + Bandit)
- **5 Kyverno ClusterPolicies** for admission control
- **Canary: 20 % → 50 % → 100 %** with 2-minute pauses (Argo Rollouts)
- **3 LLM providers** supported via one Terraform variable
- **~$1.50 per 2-hour demo · $0 when destroyed**

---

## Interview talking points (2-minute pitches you can rehearse)

### If asked "walk me through your favourite project"

> I built a platform called IntelliOps. It's an AWS EKS cluster with GitOps, canary deploys, and full observability — but the differentiator is the AI layer. When CloudWatch fires an alarm, three Lambdas subscribe. One calls Claude on Bedrock to generate a plain-English root cause using the actual error logs and past incident history. The second Lambda auto-remediates safe categories through the Kubernetes API. The third posts a Slack approval for actions that need a human — like rolling back a bad deploy. The whole loop is under 3 minutes end-to-end.
>
> What I'm most proud of is that the LLM layer is provider-agnostic via LiteLLM — one Terraform variable switches between Bedrock, OpenAI, and Gemini with the same code path. That's a real production concern about vendor lock-in that I wanted to design in from day one.

### If asked "how did you approach cost / trade-offs?"

> Two examples. First, for anomaly detection I built a full SageMaker LSTM notebook that shows I can train a custom model — but the runtime path uses CloudWatch managed anomaly detection, which is 5 dollars a month versus 72 dollars for a SageMaker endpoint. The LSTM stays in the repo as a portfolio artifact, but the deploy uses the right tool for the actual scale.
>
> Second, the full stack costs about a hundred and seventy a month if left running because of EKS control plane and NAT Gateway. So I wrote a `make destroy` path that tears everything down to zero in fifteen minutes. Demo sessions cost about a dollar fifty each. I think a lot about what things actually cost.

### If asked "the hardest thing you solved"

> Autonomous remediation from Lambda into EKS was tricky. Lambda needs to authenticate to the Kubernetes API from outside the cluster. I ended up using STS-signed presigned URLs — which is what `aws eks get-token` does internally — so the Lambda only needs boto3, no extra `eks-token` package. Then EKS Access Entries map the Lambda's IAM role to a Kubernetes group, so the API server accepts the token. No aws-auth ConfigMap editing. Clean, modern pattern.

---

## For different job targets — which bullets to lead with

| Role you're applying for | Lead with these bullets |
|---|---|
| **Platform Engineer** | 10 Terragrunt modules · GitOps + canary · IRSA + Access Entries |
| **SRE** | Auto-remediation Lambdas · MTTR reduction via LLM RCA · Slack-approved rollback flow |
| **MLOps / AI Engineer** | Multi-LLM LiteLLM abstraction · SageMaker LSTM notebook · Bedrock Claude prompt engineering |
| **DevOps Engineer** | 5-gate DevSecOps CI · GitHub Actions → ArgoCD → Argo Rollouts canary |
| **Security Engineer** | Gitleaks hard gate · Kyverno + Falco + Trivy Operator + ESO · HMAC callback verification |
| **Cloud Engineer** | Karpenter v1 spot autoscaling · CloudWatch alarms + Container Insights + Application Signals |

---

## Repository & demo assets

- **Repo:** [github.com/mrsrujan/IntelliOps](https://github.com/mrsrujan/IntelliOps)
- **README:** high-level architecture, phases, quick-start
- **docs/architecture.md:** 7 detailed Mermaid diagrams (CI/CD, platform, anomaly flow, canary, Terraform modules, security layer, component summary)
- **construct.md** / **construct-windows.md:** step-by-step AWS deploy guides with cost breakdown and troubleshooting
- **cv.md:** this file

If a recruiter or hiring manager clicks the link, the README's Mermaid diagram loads immediately — they see the AI layer, Bedrock, ArgoCD, canary, Slack, security add-ons — all before scrolling. That first-impression matters.

---

## One last thing — how to actually place it on a CV

- **Under Projects**, not under Work Experience (unless you're a consultant who was paid for it)
- Right after your most recent job, before older work
- Include the GitHub link inline — recruiters click 60%+ of the time when it's right there
- Match the length to your CV's other project entries — a 2-line CV project among 6-bullet ones looks lazy, and vice versa
- If the CV template supports a "Selected Projects" section with 3-4 items, this one goes first (because AI + infra is a rare combination)
