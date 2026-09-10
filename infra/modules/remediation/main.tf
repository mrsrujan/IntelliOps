# ── Shared Lambda source builder ──────────────────────────────────────────────
# var.lambda_source_root is absolute, passed from terragrunt.hcl. Terragrunt
# copies module source into .terragrunt-cache/HASH/HASH/, so any relative
# walk-up from path.module lands nowhere.
locals {
  # abspath() normalises the walk-up so Windows cmd.exe doesn't mangle
  # arguments that contain ../ components.
  lambda_root  = abspath(var.lambda_source_root)
  build_root   = abspath("${path.module}/build")
  build_script = abspath("${var.lambda_source_root}/build_function.py")
  lambdas = {
    remediator        = "remediator"        # auto-action: scale / restart / cordon
    rollback_request  = "rollback_request"  # posts Slack approval message
    rollback_execute  = "rollback_execute"  # API GW target — actually rolls back
  }
}

resource "null_resource" "build" {
  for_each = local.lambdas

  triggers = {
    src = sha1(join("", [
      for f in fileset("${local.lambda_root}/${each.value}", "*.py") :
      filesha256("${local.lambda_root}/${each.value}/${f}")
    ]))
    req = filesha256("${local.lambda_root}/${each.value}/requirements.txt")
  }

  # PowerShell interpreter (not the default cmd.exe) — see the lambda
  # module's build step for why. cmd mangles quoted paths starting with
  # a drive letter; PowerShell doesn't.
  provisioner "local-exec" {
    interpreter = ["powershell", "-NoProfile", "-Command"]
    command     = "& py '${local.build_script}' '${local.lambda_root}/${each.value}' '${local.build_root}/${each.value}'"
  }
}

data "archive_file" "zip" {
  for_each   = local.lambdas
  type       = "zip"
  source_dir = "${local.build_root}/${each.value}"
  output_path = "${path.module}/${each.value}.zip"
  depends_on = [null_resource.build]
}

# ── S3 upload for Lambda zips (shared bucket from the lambda module) ─────────
resource "aws_s3_object" "zip" {
  for_each    = local.lambdas
  bucket      = var.lambda_artifacts_bucket
  key         = "${each.value}/${data.archive_file.zip[each.key].output_base64sha256}.zip"
  source      = data.archive_file.zip[each.key].output_path
  source_hash = data.archive_file.zip[each.key].output_base64sha256
}

# ── IAM role shared by all remediation Lambdas ────────────────────────────────
resource "aws_iam_role" "remediation" {
  name = "${var.project}-${var.environment}-remediation"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "basic" {
  role       = aws_iam_role.remediation.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# EKS API access — needs describe-cluster to fetch endpoint & CA
resource "aws_iam_role_policy" "eks_describe" {
  name = "eks-describe"
  role = aws_iam_role.remediation.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["eks:DescribeCluster", "eks:ListClusters"]
      Resource = "*"
    }]
  })
}

# DynamoDB — write action audit records
resource "aws_iam_role_policy" "dynamodb" {
  name = "dynamodb-write"
  role = aws_iam_role.remediation.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["dynamodb:PutItem", "dynamodb:UpdateItem"]
      Resource = var.dynamodb_table_arn
    }]
  })
}

# Secrets — read Slack webhook (shared with RCA), signing secret, ArgoCD token
resource "aws_iam_role_policy" "secrets" {
  name = "secrets-read"
  role = aws_iam_role.remediation.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = concat(
        [aws_secretsmanager_secret.slack_signing.arn, aws_secretsmanager_secret.argocd_token.arn],
        var.shared_secrets_arns,
      )
    }]
  })
}

# ── EKS Access Entry — grant the Lambda role permissions inside the cluster ───
# Uses AWS's managed Admin policy for simplicity; in real production you'd
# author a custom Access Policy with only the verbs remediation needs.
resource "aws_eks_access_entry" "remediation" {
  cluster_name  = var.eks_cluster_name
  principal_arn = aws_iam_role.remediation.arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "remediation" {
  cluster_name  = var.eks_cluster_name
  principal_arn = aws_iam_role.remediation.arn
  # ClusterAdmin (full cluster-admin bind) rather than Admin (namespace-scoped).
  # Argo Rollouts CRD verbs come from the argo-rollouts-aggregate-to-admin
  # ClusterRole which merges into `admin`, but the Access Entry only actually
  # binds `admin` if `access_scope.type = "namespace"` with an explicit list.
  # `AmazonEKSClusterAdminPolicy` + `type = cluster` binds cluster-admin.
  policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}

# ── Secrets — signing secret + ArgoCD token ───────────────────────────────────
resource "aws_secretsmanager_secret" "slack_signing" {
  name        = "${var.project}/${var.environment}/slack-signing-secret"
  description = "Slack signing secret used to verify approval callbacks"
}

resource "aws_secretsmanager_secret_version" "slack_signing" {
  secret_id     = aws_secretsmanager_secret.slack_signing.id
  secret_string = jsonencode({ signing_secret = var.slack_signing_secret })
}

resource "aws_secretsmanager_secret" "argocd_token" {
  name        = "${var.project}/${var.environment}/argocd-api-token"
  description = "ArgoCD API token used by rollback_execute"
}

resource "aws_secretsmanager_secret_version" "argocd_token" {
  secret_id     = aws_secretsmanager_secret.argocd_token.id
  secret_string = jsonencode({ token = var.argocd_api_token })
}

# ── Common Lambda env ──────────────────────────────────────────────────────────
locals {
  common_env = {
    DYNAMODB_TABLE            = var.dynamodb_table_name
    EKS_CLUSTER_NAME          = var.eks_cluster_name
    AWS_REGION_NAME           = var.aws_region
    SLACK_SECRET_NAME         = var.slack_webhook_secret_name
    SLACK_SIGNING_SECRET_NAME = aws_secretsmanager_secret.slack_signing.name
    ARGOCD_TOKEN_SECRET_NAME  = aws_secretsmanager_secret.argocd_token.name
    ARGOCD_SERVER_URL         = var.argocd_server_url
    APPS_NAMESPACE            = var.apps_namespace
  }
}

# ── Lambda: remediator — handles auto-actions (scale / restart / cordon) ─────
resource "aws_lambda_function" "remediator" {
  s3_bucket        = var.lambda_artifacts_bucket
  s3_key           = aws_s3_object.zip["remediator"].key
  source_code_hash = data.archive_file.zip["remediator"].output_base64sha256
  function_name    = "${var.project}-${var.environment}-remediator"
  role             = aws_iam_role.remediation.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 512
  environment { variables = local.common_env }
}

resource "aws_sns_topic_subscription" "remediator" {
  topic_arn = var.anomalies_topic_arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.remediator.arn
  # No filter policy: CloudWatch alarm messages don't carry `anomaly_type`
  # at the top level, so we do the routing inside the Lambda instead
  # (see handler.py — unknown types return statusCode 200 with skipped=true).
}

resource "aws_lambda_permission" "remediator_sns" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.remediator.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = var.anomalies_topic_arn
}

# ── Lambda: rollback_request — posts Slack approval message ──────────────────
resource "aws_lambda_function" "rollback_request" {
  s3_bucket        = var.lambda_artifacts_bucket
  s3_key           = aws_s3_object.zip["rollback_request"].key
  source_code_hash = data.archive_file.zip["rollback_request"].output_base64sha256
  function_name    = "${var.project}-${var.environment}-rollback-request"
  role             = aws_iam_role.remediation.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 256
  environment { variables = local.common_env }
}

resource "aws_sns_topic_subscription" "rollback_request" {
  topic_arn = var.anomalies_topic_arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.rollback_request.arn
  # Routing happens in the Lambda handler — see the DeployRegression check
  # early in handler.py which returns without posting to Slack otherwise.
}

resource "aws_lambda_permission" "rollback_request_sns" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rollback_request.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = var.anomalies_topic_arn
}

# ── Lambda: rollback_execute — invoked by API Gateway on Slack button click ──
resource "aws_lambda_function" "rollback_execute" {
  s3_bucket        = var.lambda_artifacts_bucket
  s3_key           = aws_s3_object.zip["rollback_execute"].key
  source_code_hash = data.archive_file.zip["rollback_execute"].output_base64sha256
  function_name    = "${var.project}-${var.environment}-rollback-execute"
  role             = aws_iam_role.remediation.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 256
  environment { variables = local.common_env }
}

# ── API Gateway HTTP API for Slack interactive callback ───────────────────────
resource "aws_apigatewayv2_api" "slack_callback" {
  name          = "${var.project}-${var.environment}-slack-callback"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "rollback_execute" {
  api_id                 = aws_apigatewayv2_api.slack_callback.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.rollback_execute.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "rollback" {
  api_id    = aws_apigatewayv2_api.slack_callback.id
  route_key = "POST /slack/rollback"
  target    = "integrations/${aws_apigatewayv2_integration.rollback_execute.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.slack_callback.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw_invoke" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rollback_execute.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.slack_callback.execution_arn}/*/*"
}
