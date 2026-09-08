# Helm and Kubernetes providers authenticate to the EKS cluster.
#
# We use exec-based auth (invoking `aws eks get-token` at API-call time)
# instead of resolving a token upfront via data.aws_eks_cluster_auth.
# Why:
#   1. The upfront-token path caches the token at plan/apply time. STS
#      tokens are short-lived (~15 min); if the apply run itself takes
#      longer than that the cached token expires mid-way through and the
#      Helm provider starts failing with "unreachable".
#   2. Provider configs that reference data sources with depends_on can
#      end up with null values on fresh init (before the data source has
#      refreshed), producing the "no configuration has been provided"
#      error we hit here. exec doesn't have that ordering problem.
#
# Requires `aws` CLI to be on PATH where terraform runs (always true in
# our environment; terragrunt already uses it).

data "aws_eks_cluster" "this" {
  name = "${var.project}-${var.environment}"

  depends_on = [module.eks]
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.this.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", data.aws_eks_cluster.this.name, "--region", var.aws_region]
    }
  }
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.this.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", data.aws_eks_cluster.this.name, "--region", var.aws_region]
  }
}
