# IntelliOps — Architecture & Workflow Diagrams

---

## 1. End-to-End CI/CD Pipeline

```mermaid
flowchart LR
    DEV(["Developer"])

    subgraph GH ["GitHub"]
        REPO[(Repository\nmain · feature/**)]

        subgraph SECRET ["Hard Gate — Secret Scan"]
            GITLEAKS["Gitleaks\nfull git history"]
        end

        subgraph IAC ["Soft Gate — IaC Config Scan  (parallel)"]
            TRIVY_IAC["Trivy config\nhelm/ · infra/"]
        end

        subgraph CI ["GitHub Actions — CI"]
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
            CD2["⑩ argocd login (via port-forward)"]
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
        REPO[(Repo\nHelm charts · k8s manifests)]
        GHA["GitHub Actions\nCI · CD"]
    end

    subgraph AWS ["AWS Cloud — us-east-1"]
        ECR[("Amazon ECR\norder-service · payment-service · ui")]

        subgraph VPC ["VPC — 3 Availability Zones  (us-east-1a / b / c)"]
            IGW["Internet Gateway"]
            NAT["NAT Gateway"]
            ALB["Application\nLoad Balancer"]

            subgraph EKS ["Amazon EKS 1.30"]

                subgraph SYS ["System Node Group  t3.medium × 2  (tainted: CriticalAddonsOnly)"]
                    ARGOCD["ArgoCD\n+ ApplicationSet"]
                    KARPENTER_C["Karpenter Controller"]
                    ROLLOUTS_C["Argo Rollouts Controller"]
                    LBC["AWS Load Balancer Controller"]
                end

                subgraph WORK ["Workload Nodes  — Karpenter-managed  (spot + on-demand)"]

                    subgraph APPS_NS ["apps-dev namespace"]
                        SVC_UI["ui\nDeployment"]
                        SVC_PAY["payment-service\nArgo Rollout  ★ canary"]
                        SVC_ORD["order-service\nArgo Rollout  ★ canary"]
                    end

                    subgraph MON_NS ["monitoring namespace"]
                        PROM["Prometheus"]
                        GRAFANA["Grafana"]
                    end
                end
            end
        end
    end

    REPO --> GHA
    GHA -->|push image| ECR
    GHA -->|update values.yaml + sync trigger| ARGOCD
    ARGOCD -->|ApplicationSet sync| SVC_UI
    ARGOCD -->|ApplicationSet sync| SVC_PAY
    ARGOCD -->|ApplicationSet sync| SVC_ORD
    ECR -->|pull image| SVC_UI
    ECR -->|pull image| SVC_PAY
    ECR -->|pull image| SVC_ORD
    ROLLOUTS_C -->|20% → 50% → 100%| SVC_PAY
    ROLLOUTS_C -->|20% → 50% → 100%| SVC_ORD
    ALB --> SVC_UI
    LBC -.->|provisions| ALB
    SVC_UI -->|HTTP| SVC_ORD
    SVC_UI -->|HTTP| SVC_PAY
    SVC_PAY -->|/metrics| PROM
    SVC_ORD -->|/metrics| PROM
    PROM --> GRAFANA
    KARPENTER_C -->|provision nodes on demand| WORK
```

---

## 3. Canary Deployment Strategy  (Argo Rollouts)

```mermaid
flowchart LR
    START(["New image :sha\ndetected by ArgoCD"])

    subgraph ROLLOUT ["Argo Rollouts — Canary Strategy  (defined in helm/<service>/values.yaml)"]
        S1["🟡 Canary  20%\nnew pods receive 1 in 5 requests"]
        P1["⏸ Pause  2 min\nwatch error rate + latency"]
        S2["🟠 Canary  50%\nhalf traffic shifted"]
        P2["⏸ Pause  2 min\nwatch error rate + latency"]
        S3["🟢 Full  100%\nall traffic on new version"]
        S1 --> P1 --> S2 --> P2 --> S3
    end

    OK(["✅ Rollout complete\nold ReplicaSet scaled down"])
    ABORT(["❌ Manual abort\nkubectl argo rollouts abort"])

    START --> S1
    S3 --> OK
    P1 -->|"error spike / timeout"| ABORT
    P2 -->|"error spike / timeout"| ABORT
```

---

## 4. Infrastructure — Terragrunt Module Graph

```mermaid
flowchart TD
    subgraph ENVDEV ["Terragrunt — envs/dev"]
        TG_VPC["vpc unit\nterragrunt.hcl"]
        TG_ECR["ecr unit\nterragrunt.hcl"]
        TG_EKS["eks unit\nterragrunt.hcl"]
        TG_VPC --> TG_EKS
        TG_ECR --> TG_EKS
    end

    subgraph MODS ["Terraform Modules — infra/modules/"]
        MOD_VPC["vpc\n3-AZ VPC · public + private subnets\nNAT Gateway · Internet Gateway\nEKS + Karpenter discovery tags"]
        MOD_ECR["ecr\nrepos: order · payment · ui\nscan-on-push · lifecycle policies"]
        MOD_EKS["eks  terraform-aws-modules/eks v20\nEKS 1.30 · CoreDNS · VPC-CNI\nEBS CSI · public + private endpoint"]
        IRSA["IRSA Roles  (iam-role-for-service-accounts-eks)\nEBS CSI · ALB Controller · Karpenter"]
        HELM_R["Helm Releases  (inside Terraform)\nAWS Load Balancer Controller v1.8.1\nKarpenter v0.37.0"]
        SQS["SQS Queue\nKarpenter spot interruption handling"]
    end

    subgraph AWS_RES ["AWS Resources Provisioned"]
        RES_VPC[("VPC + Subnets")]
        RES_ECR[("ECR Registries")]
        RES_EKS[("EKS Cluster")]
        RES_NODES["System Node Group\nt3.medium × 2  tainted"]
        RES_WORK["Workload Node Group\nt3.large × 2  (baseline)"]
        RES_KARP["Karpenter NodePool\nspot + on-demand\nAuto consolidation"]
    end

    TG_VPC --> MOD_VPC --> RES_VPC
    TG_ECR --> MOD_ECR --> RES_ECR
    TG_EKS --> MOD_EKS --> RES_EKS
    MOD_EKS --> IRSA
    MOD_EKS --> HELM_R
    MOD_EKS --> SQS
    RES_EKS --> RES_NODES
    RES_EKS --> RES_WORK
    HELM_R --> RES_KARP
```

---

## 5. Component Summary

| Layer | Technology | Status |
|---|---|---|
| Infrastructure | Terraform + Terragrunt (VPC · ECR · EKS) | Code complete |
| Container Registry | Amazon ECR — order · payment · ui | Code complete |
| Node Autoscaling | Karpenter v0.37.0 + SQS spot interruption | Provisioned via Terraform |
| Ingress | AWS Load Balancer Controller v1.8.1 | Provisioned via Terraform |
| CI Pipeline | GitHub Actions — build · Trivy scan · push · helm lint | Complete |
| DevSecOps | Gitleaks (hard) · pip-audit · Bandit · Trivy IaC (soft) | Complete |
| CD Pipeline | GitHub Actions → ArgoCD CLI sync | Complete |
| GitOps | ArgoCD v2.12.0 + ApplicationSet | Complete |
| Canary Deploys | Argo Rollouts v1.7.2 — 20% → 50% → 100% (in Helm charts) | Complete |
| App Services | FastAPI (Python) — order · payment · ui | Complete |
| External Access | ALB Ingress on ui service | Complete |
| Observability | kube-prometheus-stack (Prometheus + Grafana) | Complete |
