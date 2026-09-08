locals {
  # abspath() normalises the ../../.. walk-up from terragrunt.hcl into a
  # clean absolute path. Windows cmd.exe mangles arguments that contain
  # ../ segments, so we abspath() EVERY path handed to local-exec —
  # including the build script itself.
  lambda_src_dir   = abspath("${var.lambda_source_root}/rca_generator")
  lambda_build_dir = abspath("${path.module}/build/rca_generator")
  build_script     = abspath("${var.lambda_source_root}/build_function.py")
}

# ── Build step: install deps and stage the Lambda source ───────────────────────
# Uses `cd` before the glob so the shell doesn't have to expand `*.py` against
# an absolute path (still fragile on Windows), and `python -m pip` instead of
# `pip` (the pip.exe shim isn't always on PATH but python.exe usually is).
resource "null_resource" "build_rca_lambda" {
  triggers = {
    handler          = filemd5("${local.lambda_src_dir}/handler.py")
    llm_client       = filemd5("${local.lambda_src_dir}/llm_client.py")
    context_builder  = filemd5("${local.lambda_src_dir}/context_builder.py")
    prompt_template  = filemd5("${local.lambda_src_dir}/prompt_template.py")
    slack_client     = filemd5("${local.lambda_src_dir}/slack_client.py")
    requirements     = filemd5("${local.lambda_src_dir}/requirements.txt")
  }

  # Invoke a small Python builder instead of shelling to bash — bash on
  # Windows (Git Bash / MSYS) can't reliably `cd` into paths that start
  # with "C:/", but Python's pathlib works identically on every OS.
  #
  # We use `py` (Python launcher) rather than `python` because the launcher
  # is what Python's Windows installer registers on PATH — the `python.exe`
  # shim isn't always present. On Linux/Mac swap to `python3`.
  provisioner "local-exec" {
    command = "py \"${local.build_script}\" \"${local.lambda_src_dir}\" \"${local.lambda_build_dir}\""
  }
}

data "archive_file" "rca_lambda_zip" {
  type        = "zip"
  source_dir  = local.lambda_build_dir
  output_path = "${path.module}/rca_generator.zip"
  depends_on  = [null_resource.build_rca_lambda]
}

# ── SNS topic — anomaly source (CloudWatch alarms or manual publish) ─────────
resource "aws_sns_topic" "anomalies" {
  name = "${var.project}-${var.environment}-anomalies"
}

# ── IAM role for the Lambda ────────────────────────────────────────────────────
resource "aws_iam_role" "rca_lambda" {
  name = "${var.project}-${var.environment}-rca-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Standard Lambda execution logging
resource "aws_iam_role_policy_attachment" "rca_basic" {
  role       = aws_iam_role.rca_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Bedrock invoke (only when provider = bedrock)
resource "aws_iam_role_policy" "bedrock_invoke" {
  count = var.llm_provider == "bedrock" ? 1 : 0
  name  = "bedrock-invoke"
  role  = aws_iam_role.rca_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["bedrock:InvokeModel"]
      Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/*"
    }]
  })
}

# Secrets Manager read (Slack always; OpenAI/Gemini conditional)
resource "aws_iam_role_policy" "secrets_read" {
  name = "secrets-read"
  role = aws_iam_role.rca_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = var.llm_secrets_arns
    }]
  })
}

# CloudWatch Logs Insights — read logs for context building
resource "aws_iam_role_policy" "logs_query" {
  name = "logs-query"
  role = aws_iam_role.rca_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:StartQuery",
        "logs:StopQuery",
        "logs:GetQueryResults",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
      ]
      Resource = "*"
    }]
  })
}

# DynamoDB — write to audit table
resource "aws_iam_role_policy" "dynamodb_write" {
  name = "dynamodb-write"
  role = aws_iam_role.rca_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["dynamodb:PutItem", "dynamodb:Query"]
      Resource = [var.dynamodb_table_arn, "${var.dynamodb_table_arn}/index/*"]
    }]
  })
}

# ── Lambda function ────────────────────────────────────────────────────────────
resource "aws_lambda_function" "rca_generator" {
  filename         = data.archive_file.rca_lambda_zip.output_path
  source_code_hash = data.archive_file.rca_lambda_zip.output_base64sha256
  function_name    = "${var.project}-${var.environment}-rca-generator"
  role             = aws_iam_role.rca_lambda.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 512

  environment {
    variables = merge(var.llm_env, {
      DYNAMODB_TABLE       = var.dynamodb_table_name
      CLOUDWATCH_LOG_GROUP = var.cloudwatch_log_group
      AWS_REGION_NAME      = var.aws_region
    })
  }
}

# ── SNS → Lambda wiring ────────────────────────────────────────────────────────
resource "aws_sns_topic_subscription" "rca_lambda" {
  topic_arn = aws_sns_topic.anomalies.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.rca_generator.arn
}

resource "aws_lambda_permission" "sns_invoke" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rca_generator.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.anomalies.arn
}
