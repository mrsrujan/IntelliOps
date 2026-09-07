# IntelliOps — Architecture & Workflow Diagrams

---

## 1. End-to-End CI/CD Pipeline

```mermaid
flowchart LR
    DEV(["👨‍💻 Developer"])

    subgraph GH ["GitHub"]
        REPO[(Repository\nmain · feature/**)]

        subgraph CI ["GitHub Actions — CI"]
            direction TB
            CI1["① Checkout + OIDC Auth"]
            CI2["② docker build\norder-service · payment-service"]
            CI3["③ Trivy scan\nCRITICAL CVE = fail"]
            CI4["④ Push :sha + :latest\nto Amazon ECR"]
            CI5["⑤ Bump image tag\nin values.yaml → git commit"]
            CI6["⑥ helm lint +\ntemplate validate"]
            CI1 --> CI2 --> CI3 --> CI4 --> CI5 --> CI6
        end

        subgraph CD ["GitHub Actions — CD  (triggers on CI success)"]
            direction TB
            CD1["⑦ OIDC Auth + kubeconfig"]
            CD2["⑧ Install ArgoCD CLI"]
            CD3["⑨ argocd app sync\npayment-service · order-service"]
            CD4["⑩ argocd app wait --health"]
            CD5["⑪ Print sync status"]
            CD1 --> CD2 --> CD3 --> CD4 --> CD5
        end
    end

    ECR[("Amazon ECR\norder-service\npayment-service")]

    subgraph EKS_BOX ["Amazon EKS"]
        ARGO["ArgoCD\nApplicationSet"]
        ROLLOUTS["Argo Rollouts"]
        APPS["apps-dev namespace\norder-service · payment-service"]
    end

    DEV -->|git push| REPO
    REPO -->|on push/PR| CI
    CI6 -->|CI success on main| CD
    CI4 -->|image push| ECR
    CI5 -->|values.yaml diff\nGitOps source of truth| ARGO
    CD3 -->|explicit sync trigger| ARGO
    ECR -->|image pull| APPS
    ARGO -->|ApplicationSet sync| APPS
    ROLLOUTS -->|canary rollout| APPS
```

---

## 2. Platform Architecture

```mermaid
flowchart TD
    DEV(["👨‍💻 Developer\ngit push"]) --> GITHUB

    subgraph GITHUB ["GitHub"]
        REPO[(Repo\nHelm charts · k8s manifests)]
        GHA["GitHub Actions\nCI · CD"]
    end

    subgraph AWS ["AWS Cloud — us-east-1"]
        ECR[("Amazon ECR\norder-service\npayment-service")]

        subgraph VPC ["VPC — 3 Availability Zones  (us-east-1a / b / c)"]
            IGW["Internet Gateway"]
            NAT["NAT Gateway"]

            subgraph EKS ["Amazon EKS 1.30"]

                subgraph SYS ["System Node Group  t3.medium × 2  (tainted: CriticalAddonsOnly)"]
                    ARGOCD["ArgoCD\n+ ApplicationSet"]
                    KARPENTER_C["Karpenter Controller"]
                    ROLLOUTS_C["Argo Rollouts Controller"]
                    LBC["AWS Load Balancer Controller"]
                end

                subgraph WORK ["Workload Nodes  — Karpenter-managed  (spot + on-demand)"]

                    subgraph APPS_NS ["apps-dev namespace"]
                        SVC_PAY["payment-service\nArgo Rollout  ★ canary"]
                        SVC_ORD["order-service\nArgo Rollout  ★ canary"]
                        SVC_UI["ui\nDeployment"]
                    end

                    subgraph MON_NS ["monitoring namespace  ← Phase 3"]
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
    ARGOCD -->|ApplicationSet sync| SVC_PAY
    ARGOCD -->|ApplicationSet sync| SVC_ORD
    ECR -->|pull image| SVC_PAY
    ECR -->|pull image| SVC_ORD
    ROLLOUTS_C -->|20% → 50% → 100%| SVC_PAY
    ROLLOUTS_C -->|20% → 50% → 100%| SVC_ORD
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

    subgraph ROLLOUT ["Argo Rollouts — Canary Strategy"]
        S1["🟡 Canary  20%\nnew pods receive 1 in 5 requests"]
        P1["⏸ Pause  2 min\nwatch error rate + latency"]
        S2["🟠 Canary  50%\nhalf traffic shifted"]
        P2["⏸ Pause  2 min\nwatch error rate + latency"]
        S3["🟢 Full  100%\nall traffic on new version"]
        S1 --> P1 --> S2 --> P2 --> S3
    end

    OK(["✅ Rollout complete\nold pods terminated"])
    ABORT(["❌ Manual abort\nargocd app rollback"])

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
        MOD_VPC["vpc\n3-AZ VPC · public + private subnets\nNAT Gateway · Internet Gateway"]
        MOD_ECR["ecr\nECR repos per service\nimage scanning enabled"]
        MOD_EKS["eks  terraform-aws-modules/eks v20\nEKS 1.30 · CoreDNS · VPC-CNI\nEBS CSI · public + private endpoint"]
        IRSA["IRSA Roles  (via iam-role-for-service-accounts-eks)\nEBS CSI · ALB Controller · Karpenter"]
        HELM_R["Helm Releases  (inside Terraform)\nAWS Load Balancer Controller v1.8.1\nKarpenter v0.37.0"]
        SQS["SQS Queue\nKarpenter spot interruption handling"]
    end

    subgraph AWS_RES ["AWS Resources Provisioned"]
        RES_VPC[("VPC + Subnets")]
        RES_ECR[("ECR Registries")]
        RES_EKS[("EKS Cluster\n+ Node Groups")]
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
| Infrastructure | Terraform + Terragrunt (VPC · ECR · EKS) | Code complete, not applied |
| Container Registry | Amazon ECR | Code complete, not applied |
| Node Autoscaling | Karpenter v0.37.0 + SQS spot interruption | Provisioned via Terraform |
| Ingress | AWS Load Balancer Controller v1.8.1 | Provisioned via Terraform |
| CI Pipeline | GitHub Actions — build · Trivy scan · push · helm lint | Done |
| CD Pipeline | GitHub Actions → ArgoCD CLI sync | Done |
| GitOps | ArgoCD v2.12.0 + ApplicationSet | Done |
| Canary Deploys | Argo Rollouts v1.7.2 — 20% → 50% → 100% | Done |
| App Services | FastAPI (Python) — order · payment · ui | Done |
| Observability | Prometheus + Grafana | Local only — Phase 3 pending |
| Secrets | — | Not yet implemented |
