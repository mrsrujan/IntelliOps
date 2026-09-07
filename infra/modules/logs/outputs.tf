output "log_group_name" {
  value = aws_cloudwatch_log_group.apps.name
}

output "log_group_arn" {
  value = aws_cloudwatch_log_group.apps.arn
}

output "fluentbit_role_arn" {
  value = module.fluentbit_irsa.iam_role_arn
}
