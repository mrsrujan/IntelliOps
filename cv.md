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

---

# Interviewer Questions — Prepared Answers

Two questions come up in almost every interview once they see IntelliOps on your resume. Here are the answers, structured so you can rehearse them at three lengths depending on how much runway the interviewer gives you.

---

## Q1: "Explain me about your project."

This is the opener. The interviewer wants to see whether you can **structure a technical explanation**, not just recite features. Lead with the **problem**, then the **shape** of the solution, then the **differentiator**, and finish with an **invitation to dig deeper**.

### 30-second version (elevator / callback screen)

> IntelliOps is an AWS EKS platform I built where LLMs analyze production anomalies and Lambda functions autonomously remediate them. When CloudWatch fires an alarm, three Lambdas subscribe — one calls Claude on Bedrock to generate a plain-English root cause using live logs and past incidents, one auto-remediates safe things like scaling pods or cordoning nodes, and one posts a Slack approval flow for risky actions like deployment rollback. The LLM layer is provider-agnostic via LiteLLM — same code path works with Bedrock, OpenAI, or Gemini, chosen at deploy time by one Terraform variable.

### 90-second version (standard first-round interview)

> The problem I wanted to solve: most monitoring stacks give you alerts, but not answers. You get paged at 2 AM and spend the first 20 minutes reading dashboards trying to figure out what changed. I wanted to build a system where the alert itself arrives with a root-cause narrative, and the safe remediations happen without me having to do anything.
>
> So I built IntelliOps. It's an AWS EKS 1.33 cluster with GitOps via ArgoCD, canary deploys via Argo Rollouts — the standard cloud-native platform pieces. On top of that I layered an AI-driven remediation loop:
>
> 1. Structured logs from FastAPI services ship to CloudWatch via Fluent Bit
> 2. CloudWatch alarms detect anomalies — error rate spikes, CPU pressure, memory pressure
> 3. Alarms publish to SNS, which fans out to **three Lambdas in parallel**
> 4. The first is an RCA Lambda — it uses LiteLLM to call Claude Sonnet 4.6 on Bedrock, giving Claude the last 30 minutes of error logs plus similar past incidents from a DynamoDB audit table. Claude returns a structured response with root cause, blast radius, recommended action, and a confidence rating. That goes to Slack.
> 5. The second is a remediator Lambda that talks to the EKS API through IRSA and Access Entries. Safe categories — CPU high, memory pressure, node not ready — auto-execute scale, restart, or cordon.
> 6. The third handles risky actions. If it's a deployment regression, we don't auto-rollback — we post an interactive Slack message with Approve / Reject buttons. Clicking Approve round-trips through API Gateway to a rollback Lambda that HMAC-verifies the Slack signature and calls the ArgoCD API.
>
> The whole loop is under 3 minutes end-to-end. And because I used LiteLLM as the abstraction layer, the LLM provider is a deploy-time choice — one Terraform variable switches between Bedrock, OpenAI GPT-4o, or Gemini 2.0 without any code change.
>
> What was interesting to build was the tiered remediation model — figuring out which actions are safe enough to auto-execute versus which need a human in the loop. Happy to go deeper on any layer.

### 2-3 minute version (deep-dive / panel interview)

Same as the 90-second version, plus these follow-ons after each layer:

**After "Structured logs":** Every service emits JSON logs with an `X-Request-ID` header propagated end-to-end, so Claude can trace one user action across order-service, payment-service, and the UI. That correlation is what makes the RCA specific instead of generic.

**After "CloudWatch alarms detect anomalies":** I made a deliberate choice to use CloudWatch Anomaly Detection alarms instead of building a custom SageMaker LSTM. The LSTM notebook is in the repo as an ML artifact showing I *can* build the model, but the runtime uses managed detectors to avoid a $72/month SageMaker endpoint. It's a "right tool for the job" call I documented explicitly.

**After "The first is an RCA Lambda":** The prompt is deliberately structured — I ask Claude for root cause, blast radius, recommended action, and confidence, in that order, under 200 words. Structured output means the Slack message is scannable and consistent regardless of which LLM provider is behind it.

**After "The second is a remediator Lambda":** The EKS API access from Lambda was actually the hardest part. Lambda runs outside the cluster, and the Kubernetes API server won't accept just any IAM identity. I ended up generating STS-signed presigned URLs the way `aws eks get-token` does internally — no `eks-token` package dependency, just boto3. Then EKS Access Entries map the Lambda's IAM role to a Kubernetes group with the specific verbs remediation needs. Clean and modern — no `aws-auth` ConfigMap editing.

**After "The third handles risky actions":** The Slack callback flow is a real production security concern. Anyone could send a POST to my API Gateway URL. I verify Slack's HMAC-SHA256 signature over the raw request body against the app's signing secret, with a 5-minute freshness window so replay attacks fail. That's the standard Slack Bolt pattern implemented from scratch.

**Closing:** The whole project has 15 commits telling a real engineering story — Phase 1 through Phase 6 plus documentation. About 3,500 lines of Terraform in 10 modular Terragrunt units, ~1,200 lines of Python across 4 Lambdas, plus the service code. Full teardown returns to $0 in about 15 minutes, so I can spin the whole thing up for a demo and destroy it after.

### Delivery tips

- **Never lead with the tech stack.** "I used Kubernetes, Terraform, Lambda…" bores interviewers instantly. Lead with the problem.
- **Use the phrase "under 3 minutes end-to-end"** — it's concrete and memorable.
- **Say "LiteLLM" out loud once.** Not everyone knows it. If they don't ask, you can drop a one-line explanation: "LiteLLM is an open-source library that gives one unified API for a hundred-plus LLM providers." Signals current knowledge.
- **Finish with an invitation:** "Happy to go deeper on any layer" or "Which part would be most useful to walk through?" — puts the interviewer in the driver's seat instead of monologuing.

---

## Q2: "Are there any direct tools or AWS services that already do this?"

This is a **challenge question** — and a really important one. The interviewer wants to know:

1. **Are you aware of the AWS / vendor landscape?** (If you say "no, nothing like this exists," you look naive.)
2. **Did you choose custom vs. managed thoughtfully?** (Or did you build this because you didn't know the alternatives?)
3. **Can you defend your architectural decisions when pushed?**

The right answer acknowledges the alternatives honestly, explains what they *do* cover, and then explains the specific gap IntelliOps fills. Never say "there's nothing like this" — always say "here's what's out there, here's where the gap is."

### The honest answer (60 seconds)

> Yes, absolutely — there are several. The closest managed AWS equivalents are **Amazon DevOps Guru** for anomaly detection and recommendations, **Amazon Q Developer** and **Amazon Q for CloudWatch** for natural-language log queries, and **AWS Systems Manager Automation** for runbook-style remediation. On the third-party side, **Datadog Watchdog**, **Dynatrace Davis AI**, and **PagerDuty AIOps** all do variations of anomaly detection with AI-assisted RCA.
>
> What none of them do out-of-the-box is the specific combination IntelliOps does:
>
> - **Provider-agnostic LLM** — DevOps Guru and Q use AWS-hosted models with no choice; Datadog and Dynatrace use their own models. If your organization has a policy about which LLM vendors are approved, or you want to A/B test Claude vs GPT-4o for RCA quality, these tools don't let you.
> - **Custom prompt engineering** — DevOps Guru returns templated recommendations, not narratives. Amazon Q gives generic answers about AWS docs. IntelliOps hands Claude the actual error logs plus similar past incidents from DynamoDB, so the RCA is specific to *your* workload's history.
> - **Kubernetes-native auto-remediation** — DevOps Guru fires alerts; you wire up the remediation yourself with Systems Manager or Lambda. IntelliOps closes the loop end-to-end.
> - **Human-in-loop rollback** with signed callbacks — none of the managed services have a pattern this specific.
>
> The way I'd frame it in a real production context: use DevOps Guru or Datadog as a *complementary* layer, not a replacement. They handle the broad set of AWS resources very well. IntelliOps-style custom logic handles the domain-specific parts — the parts where you actually understand your service better than a generic ML model does. In practice you'd probably use both.

### The shorter, more confident answer (30 seconds)

> Yes — Amazon DevOps Guru is the closest managed equivalent, plus Datadog Watchdog and Dynatrace Davis on the third-party side. They all do good anomaly detection with generic AI-assisted RCA. What they don't do is let you choose your LLM provider, use your workload's actual log history for prompts, or close the loop with Kubernetes-native auto-remediation. In production you'd probably use them alongside something like IntelliOps rather than instead of.

### Follow-up hooks the interviewer might use

If they push further, be ready with:

**"So why didn't you just use DevOps Guru?"**
> Two reasons. First, this is a portfolio project — I wanted to demonstrate that I can build the pipeline myself, not just enable a managed service. Second, DevOps Guru gives you black-box ML with no customization. If you want to tune the anomaly threshold, adjust the RCA prompt, or add new remediation actions, you can't. IntelliOps is opinionated but every piece is transparent and modifiable.

**"Isn't this reinventing the wheel?"**
> Partially, yes — and I'd absolutely use managed services for standard-case monitoring in production. What's not reinvention is the *LLM abstraction layer* and the *tiered remediation model*. Those aren't offered as products anywhere I've seen. The custom parts are the parts worth writing; the standard parts I lifted from managed offerings where I could.

**"How would you scale this to a hundred services?"**
> The current design already scales — the Lambdas are stateless, CloudWatch alarms scale linearly per metric, SNS fan-out handles thousands of events per second. The bottleneck would be Bedrock token cost, which scales with the number of alarms firing, not services deployed. At a hundred services, I'd add: PromQL-based custom alarms per service using ServiceMonitor, a batching layer that groups related alarms into single incidents before invoking the RCA Lambda, and probably a caching layer for common RCA responses.

**"What would you change if you built this again?"**
> Three things. One, I'd start with a Kubernetes-native admission-controlled autoscaler (Karpenter with Provisioners v1 from day one — I had to migrate from v1beta1). Two, I'd move the rollback Lambda into the VPC from day one so it can reach ArgoCD's ClusterIP service; right now it's a dry-run for that reason. Three, I'd use Bedrock Guardrails to filter PII from prompts before Claude sees them — for a portfolio it's fine, but production absolutely needs that.

### Comparison table (memorise the shape, not the details)

If you want to have a visual reference ready:

| Capability | DevOps Guru | Datadog Watchdog | Dynatrace Davis | **IntelliOps** |
|---|---|---|---|---|
| Anomaly detection | ✅ Managed ML | ✅ Managed ML | ✅ Managed ML | ✅ CloudWatch alarms (managed) + optional LSTM |
| AI-generated RCA narrative | Templated | Generic | Generic | ✅ Custom Claude prompt with your logs + incident history |
| Choose your LLM provider | ❌ AWS-hosted only | ❌ Datadog-only | ❌ Dynatrace-only | ✅ Bedrock / OpenAI / Gemini (deploy-time flag) |
| K8s-aware auto-remediation | ❌ Recommendations only | ❌ | Partial | ✅ EKS API via IRSA |
| Human-approved rollback with signed callback | ❌ | ❌ | ❌ | ✅ Slack HMAC callback via API Gateway |
| Custom prompt engineering | ❌ | ❌ | Limited | ✅ Full control |
| Setup complexity | Low | Low | Low | Higher (but transparent) |
| Cost model | Per resource ($$$ at scale) | Per host ($$$) | Per host ($$$) | Pay per Bedrock token + minimal AWS glue |

The pattern to notice: managed services trade **customization** for **low setup**. IntelliOps trades higher setup for full control. Both are valid — depends on the workload and team.

---

## Bonus: the "why did you build this" question

Sometimes the interviewer skips the technical opener and asks the softer question: *why did you build this?* Prepared answer:

> Two reasons. First, I wanted to prove to myself that I could combine three disciplines that usually live in separate teams — Platform Engineering, SRE, and MLOps — into one coherent architecture. Most portfolio projects show one layer; I wanted mine to span the whole story. Second, I think the direction the industry is going is AI-augmented operations — not chatbots, but LLMs as operational primitives inside real event pipelines. I wanted hands-on experience designing that pattern before it becomes standard, so I could bring it into a team already having done it once.

That answer signals: strategic thinking, cross-discipline range, and forward-looking curiosity. All qualities you want on the record.
