output "alarm_names" {
  value = concat(
    [for a in aws_cloudwatch_metric_alarm.high_cpu : a.alarm_name],
    [for a in aws_cloudwatch_metric_alarm.high_memory : a.alarm_name],
    [for a in aws_cloudwatch_metric_alarm.high_error_rate : a.alarm_name],
  )
}

output "container_insights_addon_status" {
  value = aws_eks_addon.cloudwatch.addon_version
}
