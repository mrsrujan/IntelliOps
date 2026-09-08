# Helm and Kubernetes providers authenticate to the EKS cluster.
#
# Design choices:
#   1. Use module.eks outputs directly instead of the aws_eks_cluster
#      data source. The data source + depends_on pattern is known to
#      return null/stale values on some `terraform init` scenarios,
#      producing "Kubernetes cluster unreachable: no configuration
#      has been provided" errors. Module outputs don't have that race.
#
#   2. exec-based auth (invoking `aws eks get-token` at API-call time)
#      instead of a cached token. STS tokens live ~15 minutes; long
#      applies can outlast a cached token and start seeing "unreachable"
#      errors half-way through.
#
# Trade-off: on the very first apply (cluster doesn't exist yet),
# module.eks.cluster_endpoint is unknown, so Terraform errors early
# with a clearer "unknown value" message. That's fine — the first
# apply provisions the cluster; the second apply installs the Helm
# releases. That two-pass pattern is documented in the eks module's
# own examples.
#
# Requires the `aws` CLI on PATH where terraform runs.

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args = [
        "eks", "get-token",
        "--cluster-name", module.eks.cluster_name,
        "--region", var.aws_region,
      ]
    }
  }
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args = [
      "eks", "get-token",
      "--cluster-name", module.eks.cluster_name,
      "--region", var.aws_region,
    ]
  }
}
