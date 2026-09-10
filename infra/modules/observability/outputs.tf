output "alarm_names" {
  value = [for a in aws_cloudwatch_metric_alarm.high_error_rate : a.alarm_name]
}

output "container_insights_addon_status" {
  value = aws_eks_addon.cloudwatch.addon_version
}
