resource "aws_kinesis_stream" "metrics" {
  name             = "${var.project}-${var.environment}-metrics"
  retention_period = 24
  shard_count      = 1

  stream_mode_details {
    stream_mode = "PROVISIONED"
  }
}

resource "aws_kinesis_stream" "events" {
  name             = "${var.project}-${var.environment}-events"
  retention_period = 24
  shard_count      = 1

  stream_mode_details {
    stream_mode = "PROVISIONED"
  }
}
