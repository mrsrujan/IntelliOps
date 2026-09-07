output "slack_callback_url" {
  value       = "${aws_apigatewayv2_api.slack_callback.api_endpoint}/slack/rollback"
  description = "Paste this into the Slack app's Interactivity Request URL"
}

output "remediator_function_name" {
  value = aws_lambda_function.remediator.function_name
}

output "rollback_request_function_name" {
  value = aws_lambda_function.rollback_request.function_name
}

output "rollback_execute_function_name" {
  value = aws_lambda_function.rollback_execute.function_name
}
