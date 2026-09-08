# ── Container Insights + Application Signals ─────────────────────────────────
# The `amazon-cloudwatch-observability` add-on installs the CloudWatch agent
# (pod CPU/memory metrics for Container Insights) and a Fluent Bit DaemonSet.
# We already have Fluent Bit from Phase 3, so we disable the add-on's log
# shipping to avoid double-shipping every container log.
#
# We also opt in to Application Signals — AWS's OpenTelemetry-based APM/
# tracing layer bundled with the add-on. Free to enable, billed per span.
# Provides golden-signal SLOs and distributed traces without a separate
# X-Ray/Jaeger install.
resource "aws_eks_addon" "cloudwatch" {
  cluster_name = var.eks_cluster_name
  addon_name   = "amazon-cloudwatch-observability"

  configuration_values = jsonencode({
    containerLogs = {
      enabled = false
    }
    agent = {
      config = {
        traces = {
          traces_collected = {
            application_signals = {}
          }
        }
        logs = {
          metrics_collected = {
            application_signals = {}
          }
        }
      }
    }
  })
}

# ── CloudWatch Logs → CloudWatch Metrics ──────────────────────────────────────
# One metric filter per service, counting any WARN/ERROR log entry.
# The apps emit structured JSON, so we filter by $.level and $.service.
resource "aws_cloudwatch_log_metric_filter" "errors" {
  for_each = toset(var.services)

  name           = "${var.project}-${var.environment}-errors-${each.key}"
  log_group_name = var.log_group_name
  pattern        = "{ ($.level = \"ERROR\" || $.level = \"WARNING\") && $.service = \"${each.key}\" }"

  metric_transformation {
    name          = "ErrorCount"
    namespace     = "IntelliOps/${each.key}"
    value         = "1"
    default_value = "0"
  }
}

# ── Alarms ────────────────────────────────────────────────────────────────────
# Naming convention: intelliops-<env>-<AnomalyType>-<service>
# The Lambdas parse the service and anomaly type back out of AlarmName.

resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  for_each = toset(var.services)

  alarm_name          = "${var.project}-${var.environment}-HighErrorRate-${each.key}"
  alarm_description   = "Error/warning log rate exceeded 5/min on ${each.key}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ErrorCount"
  namespace           = "IntelliOps/${each.key}"
  period              = 60
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.anomalies_topic_arn]

  depends_on = [aws_cloudwatch_log_metric_filter.errors]
}

resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  for_each = toset(var.services)

  alarm_name          = "${var.project}-${var.environment}-HighCPU-${each.key}"
  alarm_description   = "Max pod CPU utilisation exceeded 80% on ${each.key}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 80
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.anomalies_topic_arn]

  metric_query {
    id          = "cpu"
    return_data = true
    expression  = format(
      "MAX(SEARCH('{ContainerInsights,ClusterName,Namespace,PodName} MetricName=\"pod_cpu_utilization\" ClusterName=\"%s\" Namespace=\"%s\" PodName^=\"%s-dev\"', 'Average', 60))",
      var.eks_cluster_name,
      var.apps_namespace,
      each.key,
    )
    label = "${each.key} max pod CPU"
  }

  depends_on = [aws_eks_addon.cloudwatch]
}

resource "aws_cloudwatch_metric_alarm" "high_memory" {
  for_each = toset(var.services)

  alarm_name          = "${var.project}-${var.environment}-MemoryPressure-${each.key}"
  alarm_description   = "Max pod memory utilisation exceeded 80% on ${each.key}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 80
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.anomalies_topic_arn]

  metric_query {
    id          = "mem"
    return_data = true
    expression  = format(
      "MAX(SEARCH('{ContainerInsights,ClusterName,Namespace,PodName} MetricName=\"pod_memory_utilization\" ClusterName=\"%s\" Namespace=\"%s\" PodName^=\"%s-dev\"', 'Average', 60))",
      var.eks_cluster_name,
      var.apps_namespace,
      each.key,
    )
    label = "${each.key} max pod memory"
  }

  depends_on = [aws_eks_addon.cloudwatch]
}
