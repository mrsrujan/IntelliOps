# IntelliOps — Architecture & Workflow Diagrams

---

## 1. End-to-End CI/CD Pipeline

```mermaid
flowchart LR
    DEV(["Developer"])

    subgraph GH ["GitHub"]
        REPO[(Repository)]

        subgraph SECRET ["Hard Gate — Secret Scan"]
            GITLEAKS["Gitleaks\nfull git history"]
        end

        subgraph IAC ["Soft Gate — IaC Config Scan  (parallel)"]
            TRIVY_IAC["Trivy config\nhelm/ · infra/"]
        end

        subgraph CI ["GitHub Actions — CI  (per service)"]
            direction TB
            CI1["① Checkout + OIDC Auth"]
            CI2["② unit tests"]
            CI3["③ pip-audit  (soft)"]
            CI4["④ Bandit SAST  (soft)"]
            CI5["⑤ docker build"]
            CI6["⑥ Trivy image scan\nCRITICAL = hard fail"]
            CI7["⑦ push :sha + :latest → ECR"]
            CI8["⑧ bump values.yaml\ngit rebase + push"]
            CI1 --> CI2 --> CI3 --> CI4 --> CI5 --> CI6 --> CI7 --> CI8
        end

        HELM_LINT["Helm Lint + template validate"]

        subgraph CD ["GitHub Actions — CD  (on CI success)"]
            direction TB
            CD1["⑨ OIDC Auth + kubeconfig"]
            CD2["⑩ argocd login"]
            CD3["⑪ argocd app sync\npayment · order · ui"]
            CD4["⑫ argocd app wait --health"]
            CD1 --> CD2 --> CD3 --> CD4
        end
    end

    ECR[("Amazon ECR")]

    subgraph EKS_BOX ["Amazon EKS"]
        ARGO["ArgoCD\nApplicationSet"]
        ROLLOUTS["Argo Rollouts\ncanary 20 → 50 → 100"]
        APPS["apps-dev namespace"]
    end

    DEV -->|git push| REPO
    REPO --> GITLEAKS
    GITLEAKS --> IAC
    GITLEAKS --> CI
    CI --> HELM_LINT
    HELM_LINT --> CD
    CI7 --> ECR
    CI8 -->|values.yaml diff| ARGO
    CD3 -->|explicit sync| ARGO
    ECR -->|pull image| APPS
    ARGO -->|ApplicationSet sync| APPS
    ROLLOUTS --> APPS
```

---

## 2. Platform Architecture

```mermaid
flowchart TD
    USER(["End user"]) -->|HTTP| ALB
    DEV(["Developer\ngit push"]) --> GITHUB

    subgraph GITHUB ["GitHub"]
        REPO[(Repo\nHelm · Terraform · Lambda code)]
        GHA["GitHub Actions\nCI · CD · Chaos"]
    end

    subgraph AWS ["AWS Cloud — us-east-1"]
        ECR[("Amazon ECR\norder · payment · ui")]
        SNS_TOPIC["SNS  anomalies"]
        DYNAMODB[("DynamoDB\nincidents audit")]
        SECRETS[("Secrets Manager\nLLM keys · Slack · ArgoCD")]

        subgraph AI_LAYER ["AI / Remediation Layer  (Lambda)"]
            RCA["RCA Lambda\nLiteLLM → Bedrock / OpenAI / Gemini"]
            REMED["Remediator Lambda\nscale · restart · cordon"]
            RB_REQ["Rollback Request\n→ Slack approval"]
            RB_EXE["Rollback Execute\nAPI GW target"]
        end

        BEDROCK[("Amazon Bedrock\nClaude Sonnet 4.6")]
        APIGW["API Gateway\n/slack/rollback"]

        subgraph VPC ["VPC — 3 AZs"]
            IGW["Internet Gateway"]
            NAT["NAT Gateway"]
            ALB["Application\nLoad Balancer"]

            subgraph EKS ["Amazon EKS 1.33"]

                subgraph SYS ["System Node Group  (tainted)"]
                    ARGOCD["ArgoCD\n+ ApplicationSet"]
                    KARPENTER_C["Karpenter"]
                    ROLLOUTS_C["Argo Rollouts"]
                    LBC["AWS LB Controller"]
                    FLUENTBIT["Fluent Bit\n(logs)"]
                end

                subgraph WORK ["Workload Nodes  (Karpenter spot + on-demand)"]

                    subgraph APPS_NS ["apps-dev  (NetworkPolicies)"]
                        SVC_UI["ui  Deployment"]
                        SVC_PAY["payment-service  Rollout ★"]
                        SVC_ORD["order-service  Rollout ★"]
                    end

                    subgraph MON_NS ["monitoring"]
                        PROM["Prometheus"]
                        GRAFANA["Grafana"]
                    end

                    subgraph SEC_NS ["security"]
                        KYVERNO["Kyverno"]
                        FALCO["Falco"]
                        TRIVY_OP["Trivy Operator"]
                        ESO["External Secrets"]
                    end
                end
            end
        end

        CW_LOGS[("CloudWatch Logs\n/eks/intelliops-dev/apps")]
        CW_ALARMS["CloudWatch Alarms\nHighCPU · Memory · ErrorRate"]
    end

    SLACK((Slack))

    REPO --> GHA
    GHA -->|push image| ECR
    GHA -->|update values.yaml| ARGOCD
    ARGOCD -->|sync| APPS_NS
    ECR -->|pull| APPS_NS
    ROLLOUTS_C -->|20→50→100| SVC_PAY
    ROLLOUTS_C -->|20→50→100| SVC_ORD
    ALB --> SVC_UI
    LBC -.->|provisions| ALB
    SVC_UI -->|HTTP| SVC_ORD
    SVC_UI -->|HTTP| SVC_PAY

    APPS_NS -->|/metrics| PROM
    PROM --> GRAFANA
    APPS_NS -->|stdout JSON| FLUENTBIT
    FLUENTBIT --> CW_LOGS
    CW_LOGS -->|metric filter| CW_ALARMS
    CW_ALARMS -->|state=ALARM| SNS_TOPIC

    SNS_TOPIC --> RCA
    SNS_TOPIC --> REMED
    SNS_TOPIC --> RB_REQ
    RCA --> BEDROCK
    RCA --> CW_LOGS
    RCA --> DYNAMODB
    RCA --> SECRETS
    RCA --> SLACK
    REMED -.->|k8s API + IRSA| EKS
    REMED --> DYNAMODB
    REMED --> SLACK
    RB_REQ --> SLACK
    SLACK --> APIGW
    APIGW --> RB_EXE
    RB_EXE -->|verify HMAC| SECRETS
    RB_EXE -->|POST /rollback| ARGOCD
    RB_EXE --> DYNAMODB

    KARPENTER_C -.->|provision| WORK
    KYVERNO -.->|admission control| APPS_NS
    FALCO -.->|runtime detect| SVC_PAY
    FALCO -.->|runtime detect| SVC_ORD
    TRIVY_OP -.->|scan images| APPS_NS
```

---

## 3. Anomaly → RCA → Remediation Flow

```mermaid
flowchart LR
    START(["CloudWatch alarm fires\ne.g. HighErrorRate on payment-service"])

    START --> SNS[SNS anomalies topic]

    SNS --> RCA{{"RCA Lambda"}}
    SNS --> REMED{{"Remediator Lambda"}}
    SNS --> RBR{{"Rollback Request"}}

    subgraph RCA_FLOW ["RCA — analyse and narrate"]
        RCA --> CTX["Build context\n· CloudWatch Logs Insights: last 30 min WARN/ERROR\n· DynamoDB GSI: similar incidents (7 days)"]
        CTX --> LLM["LiteLLM.completion()\nmodel=$LLM_MODEL"]
        LLM --> LLM_CHOICE{Provider}
        LLM_CHOICE -->|bedrock/*| BEDROCK[Bedrock\nClaude Sonnet 4.6]
        LLM_CHOICE -->|openai/*| OPENAI[OpenAI\nGPT-4o]
        LLM_CHOICE -->|gemini/*| GEMINI[Google\nGemini 2.0]
        BEDROCK --> RESP["Structured RCA:\nroot cause · blast radius · action · confidence"]
        OPENAI --> RESP
        GEMINI --> RESP
        RESP --> DDB1[(DynamoDB\naudit)]
        RESP --> SLACK1((Slack\nincident summary))
    end

    subgraph REM_FLOW ["Auto-remediation"]
        REMED --> DISPATCH{anomaly_type}
        DISPATCH -->|HighCPU / Memory| SCALE["scale Rollout ×10"]
        DISPATCH -->|HighErrorRate| RESTART["rollout restartAt"]
        DISPATCH -->|NodeNotReady| CORDON["node.unschedulable = true"]
        DISPATCH -->|other| SKIP((skipped))
        SCALE --> K8S[EKS API\nIRSA + Access Entry]
        RESTART --> K8S
        CORDON --> K8S
        K8S --> DDB2[(DynamoDB\naction audit)]
        K8S --> SLACK2((Slack\n✅ auto-remediated))
    end

    subgraph RB_FLOW ["Rollback approval (DeployRegression only)"]
        RBR --> RB_MSG((Slack block kit\nApprove / Reject))
        RB_MSG -->|click| APIGW[API Gateway\nPOST /slack/rollback]
        APIGW --> RB_EXE[Rollback Execute Lambda]
        RB_EXE --> SIG_VERIFY["Verify HMAC signature\n(5-min replay window)"]
        SIG_VERIFY --> ARGOCD_API[ArgoCD API\nPOST /rollback]
        ARGOCD_API --> DDB3[(DynamoDB\naudit)]
        ARGOCD_API --> SLACK3((Slack\n✅ rolled back))
    end
```

---

## 4. Canary Deployment Strategy  (Argo Rollouts)

```mermaid
flowchart LR
    NEW(["New image :sha\ndetected by ArgoCD"])

    subgraph ROLLOUT ["Canary steps (defined in helm/<service>/values.yaml)"]
        S1["🟡 Canary  20%"]
        P1["⏸ 2 min"]
        S2["🟠 Canary  50%"]
        P2["⏸ 2 min"]
        S3["🟢 Full  100%"]
        S1 --> P1 --> S2 --> P2 --> S3
    end

    OK(["✅ Rollout complete"])
    ABORT(["❌ Aborted\nAI RCA + rollback flow"])

    NEW --> S1
    S3 --> OK
    P1 -->|error spike| ABORT
    P2 -->|error spike| ABORT
```

---

## 5. Infrastructure — Terragrunt Module Graph

```mermaid
flowchart TD
    subgraph ENV ["Terragrunt — envs/dev/"]
        TG_VPC[vpc]
        TG_ECR[ecr]
        TG_EKS[eks]
        TG_LOGS[logs]
        TG_KIN[kinesis]
        TG_DDB[dynamodb]
        TG_LLM[llm]
        TG_LAMBDA[lambda]
        TG_OBS[observability]
        TG_REM[remediation]

        TG_VPC --> TG_EKS
        TG_ECR --> TG_EKS
        TG_EKS --> TG_LOGS
        TG_EKS --> TG_OBS
        TG_LAMBDA --> TG_REM
        TG_DDB --> TG_LAMBDA
        TG_LLM --> TG_LAMBDA
        TG_LOGS --> TG_LAMBDA
        TG_LOGS --> TG_OBS
        TG_LAMBDA --> TG_OBS
        TG_EKS --> TG_REM
        TG_DDB --> TG_REM
    end

    subgraph MODS ["Terraform Modules — infra/modules/"]
        M_VPC[vpc<br/>3-AZ · NAT · IGW · EKS tags]
        M_ECR[ecr<br/>order · payment · ui + lifecycle]
        M_EKS[eks<br/>1.33 · Karpenter v1 · LBC · IRSA]
        M_LOGS[logs<br/>Log Group · Fluent Bit IRSA]
        M_KIN[kinesis<br/>metrics + events streams]
        M_DDB[dynamodb<br/>incidents + service GSI]
        M_LLM[llm<br/>Secrets per provider]
        M_LAMBDA[lambda<br/>RCA + SNS anomalies]
        M_OBS[observability<br/>Container Insights + alarms]
        M_REM[remediation<br/>3 Lambdas + API GW + EKS access]
    end

    TG_VPC --> M_VPC
    TG_ECR --> M_ECR
    TG_EKS --> M_EKS
    TG_LOGS --> M_LOGS
    TG_KIN --> M_KIN
    TG_DDB --> M_DDB
    TG_LLM --> M_LLM
    TG_LAMBDA --> M_LAMBDA
    TG_OBS --> M_OBS
    TG_REM --> M_REM
```

---

## 6. Security Layer (Phase 6)

```mermaid
flowchart LR
    subgraph SHIFT_LEFT ["Shift Left — pre-cluster"]
        GITLEAKS_2[Gitleaks<br/>hard block]
        TRIVY_IMG[Trivy image scan<br/>CRITICAL hard block]
        TRIVY_CFG[Trivy IaC<br/>soft report]
        PIP[pip-audit<br/>soft report]
        BANDIT[Bandit SAST<br/>soft report]
    end

    subgraph ADMIT ["Admission — Kyverno ClusterPolicies"]
        POL1[disallow-latest-tag<br/>Audit]
        POL2[require-resource-limits<br/>Audit]
        POL3[require-non-root<br/>Audit]
        POL4[require-probes<br/>Audit]
        POL5[disallow-privileged<br/>Enforce]
    end

    subgraph RUNTIME ["Runtime — in-cluster"]
        FALCO_R[Falco DaemonSet<br/>syscall anomalies → Slack]
        TRIVY_OP_R[Trivy Operator<br/>continuous CVE + config + RBAC]
        NETPOL[NetworkPolicies<br/>default-deny + explicit allows]
        ESO_R[External Secrets Operator<br/>Secrets Manager → K8s Secrets]
    end

    SHIFT_LEFT --> ADMIT
    ADMIT --> RUNTIME
```

---

## 7. Component Summary

| Layer | Technology | Status |
|---|---|---|
| Infrastructure | Terraform + Terragrunt (10 modules) | Code complete |
| Container Registry | Amazon ECR — order · payment · ui | Code complete |
| Cluster | Amazon EKS 1.33 + Karpenter v1 + IRSA + AWS LB Controller | Code complete |
| Log Pipeline | Fluent Bit DaemonSet → CloudWatch Logs (structured JSON) | Code complete |
| Metrics | Prometheus + Grafana + kube-prometheus-stack | Code complete |
| CloudWatch | Container Insights + metric-filter alarms + SNS | Code complete |
| CI | GitHub Actions — build · Trivy · push · helm lint | Complete |
| DevSecOps CI Gates | Gitleaks (hard) · pip-audit · Bandit · Trivy IaC (soft) | Complete |
| CD | GitHub Actions → ArgoCD CLI sync | Complete |
| GitOps | ArgoCD v2.12 + ApplicationSet | Complete |
| Canary | Argo Rollouts — 20% → 50% → 100% (in Helm charts) | Complete |
| Apps | FastAPI — order · payment · ui with fault-injection endpoints | Complete |
| External Access | ALB Ingress on ui service | Complete |
| AI/ML — Runtime | LiteLLM abstraction: Bedrock Claude Sonnet 4.6 (default), OpenAI, Gemini | Complete |
| AI/ML — Training | SageMaker LSTM notebook (reference implementation) | Complete |
| Auto-Remediation | 3 Lambdas: scale · restart · cordon (via EKS API + IRSA) | Complete |
| Rollback Flow | Slack interactive → API GW → HMAC verify → ArgoCD API | Complete |
| Audit | DynamoDB incidents table with service-index GSI | Complete |
| Streaming | Kinesis Data Streams (metrics + events) | Complete |
| Security — Admission | Kyverno + 5 baseline ClusterPolicies | Complete |
| Security — Runtime | Falco (eBPF) + Trivy Operator + Network Policies | Complete |
| Security — Secrets | External Secrets Operator + ClusterSecretStore for Secrets Manager | Complete |
