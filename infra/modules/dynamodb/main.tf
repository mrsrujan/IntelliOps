resource "aws_dynamodb_table" "incidents" {
  name         = "${var.project}-${var.environment}-incidents"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "incident_id"
  range_key    = "timestamp"

  attribute {
    name = "incident_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "service"
    type = "S"
  }

  # Query recent incidents per service for the Slack "similar incidents" hint
  global_secondary_index {
    name            = "service-index"
    hash_key        = "service"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }
}
