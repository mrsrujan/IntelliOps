output "rca_lambda_arn" {
  value = aws_lambda_function.rca_generator.arn
}

output "rca_lambda_name" {
  value = aws_lambda_function.rca_generator.function_name
}

output "anomalies_topic_arn" {
  value = aws_sns_topic.anomalies.arn
}

output "anomalies_topic_name" {
  value = aws_sns_topic.anomalies.name
}

output "lambda_artifacts_bucket" {
  value       = aws_s3_bucket.lambda_artifacts.id
  description = "S3 bucket used to host Lambda deployment zips (shared with remediation module)"
}
