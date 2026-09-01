# EKS cluster auth is read via data sources so the Helm/K8s providers
# can be configured without referencing module outputs (which Terraform
# does not allow inside provider blocks).
# First apply: comment out helm_release resources until the cluster exists.
# Second apply: cluster is up, data sources resolve, Helm releases run.

data "aws_eks_cluster" "this" {
  name = "${var.project}-${var.environment}"

  depends_on = [module.eks]
}

data "aws_eks_cluster_auth" "this" {
  name = "${var.project}-${var.environment}"

  depends_on = [module.eks]
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.this.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.this.token
  }
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.this.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.this.token
}
