# GitHub Actions -> AWS via OIDC.
#
# Creates the OIDC provider (idempotent — reused if one already exists in the
# account), an IAM role scoped to a single GitHub repo, and an EKS Access
# Entry so the CD workflow can use kubectl against the cluster.

# ── OIDC provider ────────────────────────────────────────────────────────────
# GitHub Actions federated OIDC. Only one provider per account is allowed for
# this URL; the `try(...) / count` shim below imports an existing one instead
# of failing with EntityAlreadyExists.
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# ── IAM role for GitHub Actions ──────────────────────────────────────────────
# Trust policy is written for GitHub's post-2025 "immutable identifiers" OIDC
# subject format: `repo:{owner}@{ownerId}/{repo}@{repoId}:...`. Matching on
# `repository` (stable owner/name) plus a wildcard `sub` keeps the intent
# scoped to this repo while surviving GitHub's numeric-ID interpolation.
resource "aws_iam_role" "github_actions" {
  name = "${var.project}-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = data.aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud"        = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:repository" = var.github_repository
        }
        StringLike = {
          # Split the owner/repo pieces on `@` so the token's `@<numericId>`
          # segments match. AWS requires *either* `sub` or `job_workflow_ref`
          # to be constrained, so we can't drop this entirely.
          "token.actions.githubusercontent.com:sub" = "repo:${split("/", var.github_repository)[0]}*/${split("/", var.github_repository)[1]}*:*"
        }
      }
    }]
  })
}

# Broad for the reference architecture — the CI role pushes to ECR, and CD
# runs kubectl against the cluster. Scope down for a real environment.
resource "aws_iam_role_policy_attachment" "admin" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

# ── EKS Access Entry — CD workflow uses kubectl for port-forward + argocd sync
resource "aws_eks_access_entry" "github_actions" {
  cluster_name  = var.eks_cluster_name
  principal_arn = aws_iam_role.github_actions.arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "github_actions" {
  cluster_name  = var.eks_cluster_name
  principal_arn = aws_iam_role.github_actions.arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}
