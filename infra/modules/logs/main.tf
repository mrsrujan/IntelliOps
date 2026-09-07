resource "aws_cloudwatch_log_group" "apps" {
  name              = "/eks/${var.project}-${var.environment}/apps"
  retention_in_days = 30
}

# IRSA role assumed by the fluent-bit DaemonSet
module "fluentbit_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "${var.project}-${var.environment}-fluentbit"

  role_policy_arns = {
    logs = aws_iam_policy.fluentbit.arn
  }

  oidc_providers = {
    main = {
      provider_arn               = var.oidc_provider_arn
      namespace_service_accounts = ["logging:fluent-bit"]
    }
  }
}

resource "aws_iam_policy" "fluentbit" {
  name        = "${var.project}-${var.environment}-fluentbit-logs"
  description = "Allow fluent-bit to write to the apps log group"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogStreams",
        "logs:DescribeLogGroups",
      ]
      Resource = "${aws_cloudwatch_log_group.apps.arn}:*"
    }]
  })
}
