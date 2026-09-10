module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "${var.project}-${var.environment}"
  cluster_version = "1.33"

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnet_ids

  enable_cluster_creator_admin_permissions = true

  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent    = true
      before_compute = true
    }
    aws-ebs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.ebs_csi_irsa.iam_role_arn
    }
  }

  # Prefix delegation on vpc-cni bumps t3.small pod capacity from 8 to ~110.
  # Kubelet's --max-pods is set at bootstrap and doesn't auto-follow the CNI
  # config, so we force it here via NodeConfig YAML injected pre-nodeadm on
  # each nodegroup (see cloudinit_pre_nodeadm below). ENABLE_PREFIX_DELEGATION
  # is set on the vpc-cni addon manually via aws-cli after cluster bring-up.
  eks_managed_node_groups = {
    system = {
      name           = "system"
      instance_types = ["t3.small"]
      min_size       = 1
      max_size       = 2
      desired_size   = 1
      cloudinit_pre_nodeadm = [{
        content_type = "application/node.eks.aws"
        content      = <<-EOT
          apiVersion: node.eks.aws/v1alpha1
          kind: NodeConfig
          spec:
            kubelet:
              config:
                maxPods: 110
              flags:
                - --max-pods=110
        EOT
      }]
      labels = {
        role = "system"
      }
      taints = [{
        key    = "CriticalAddonsOnly"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }

    workload = {
      name           = "workload"
      instance_types = ["t3.small", "t3a.small"]
      min_size       = 1
      max_size       = 3
      desired_size   = 3
      cloudinit_pre_nodeadm = [{
        content_type = "application/node.eks.aws"
        content      = <<-EOT
          apiVersion: node.eks.aws/v1alpha1
          kind: NodeConfig
          spec:
            kubelet:
              config:
                maxPods: 110
              flags:
                - --max-pods=110
        EOT
      }]
      labels = {
        role = "workload"
      }
    }
  }

  node_security_group_tags = {
    "karpenter.sh/discovery" = "${var.project}-${var.environment}"
  }
}

# IRSA for EBS CSI Driver
module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name             = "${var.project}-${var.environment}-ebs-csi"
  attach_ebs_csi_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }
}

# IRSA for AWS Load Balancer Controller
module "alb_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name                              = "${var.project}-${var.environment}-alb-controller"
  attach_load_balancer_controller_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-load-balancer-controller"]
    }
  }
}

# IRSA for Karpenter
module "karpenter_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name                          = "${var.project}-${var.environment}-karpenter"
  attach_karpenter_controller_policy = true

  karpenter_controller_cluster_name       = module.eks.cluster_name
  karpenter_controller_node_iam_role_arns = [module.eks.eks_managed_node_groups["workload"].iam_role_arn]

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["karpenter:karpenter"]
    }
  }
}

# Karpenter SQS queue for spot interruption handling
resource "aws_sqs_queue" "karpenter_interruption" {
  name                      = "${var.project}-${var.environment}-karpenter"
  message_retention_seconds = 300
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue_policy" "karpenter_interruption" {
  queue_url = aws_sqs_queue.karpenter_interruption.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = ["events.amazonaws.com", "sqs.amazonaws.com"] }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.karpenter_interruption.arn
    }]
  })
}

# Helm: AWS Load Balancer Controller
resource "helm_release" "aws_lbc" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  namespace  = "kube-system"
  version    = "1.11.0"

  set {
    name  = "clusterName"
    value = module.eks.cluster_name
  }
  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.alb_irsa.iam_role_arn
  }

  depends_on = [module.eks]
}

# Helm: Karpenter
resource "helm_release" "karpenter" {
  name       = "karpenter"
  repository = "oci://public.ecr.aws/karpenter"
  chart      = "karpenter"
  namespace  = "karpenter"
  version    = "1.5.2" # Karpenter compatibility: K8s 1.33 needs >= 1.5, K8s 1.34 needs >= 1.8

  create_namespace = true
  timeout          = 600 # 10 min — pulling the OCI image + CRDs can take a while

  # Bundle all values in one yaml block so we can express arrays and maps
  # (tolerations, nodeSelector) cleanly. The controller pods must tolerate
  # the CriticalAddonsOnly taint on our system nodes, otherwise they stay
  # Pending forever and helm_release times out.
  values = [yamlencode({
    settings = {
      clusterName       = module.eks.cluster_name
      interruptionQueue = aws_sqs_queue.karpenter_interruption.name
    }
    serviceAccount = {
      annotations = {
        "eks.amazonaws.com/role-arn" = module.karpenter_irsa.iam_role_arn
      }
    }
    # Pin the controller to system nodes and tolerate the taint that keeps
    # non-critical workloads off them.
    nodeSelector = {
      role = "system"
    }
    tolerations = [{
      key      = "CriticalAddonsOnly"
      operator = "Exists"
    }]
    # Free-Tier-restricted account only allows t3.small; the chart's default
    # 2×1Gi memory request doesn't fit alongside coredns on a single node.
    replicas = 1
    controller = {
      resources = {
        requests = { cpu = "200m", memory = "384Mi" }
        limits   = { cpu = "1", memory = "512Mi" }
      }
    }
  })]

  depends_on = [module.eks]
}
