output "metrics_stream_name" {
  value = aws_kinesis_stream.metrics.name
}

output "metrics_stream_arn" {
  value = aws_kinesis_stream.metrics.arn
}

output "events_stream_name" {
  value = aws_kinesis_stream.events.name
}

output "events_stream_arn" {
  value = aws_kinesis_stream.events.arn
}
