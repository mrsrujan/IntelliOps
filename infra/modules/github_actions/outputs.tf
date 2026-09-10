output "role_arn" {
  value       = aws_iam_role.github_actions.arn
  description = "Set this as the AWS_GITHUB_ACTIONS_ROLE repo secret."
}

output "account_id" {
  value       = data.aws_iam_openid_connect_provider.github.arn == null ? null : split(":", data.aws_iam_openid_connect_provider.github.arn)[4]
  description = "Set this as the AWS_ACCOUNT_ID repo secret. Extracted from the OIDC provider ARN so the caller doesn't have to plumb it."
}
