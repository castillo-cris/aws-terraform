############################################
# main.tf
############################################

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Etiquetas comunes
locals {
  project_name = var.project_name
  tags = {
    Project = var.project_name
    Owner   = "Cristian"
  }
}

# Empaquetado del código Lambda en ZIP (sin S3)
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda.zip"
}

# IAM Role para Lambda con mínimo privilegio (CloudWatch Logs)
resource "aws_iam_role" "lambda_exec_role" {
  name               = "${local.project_name}-lambda-exec-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

# Política administrada mínima para logs
resource "aws_iam_role_policy_attachment" "lambda_logs_attach" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda function (Python 3.10, sin layers)
resource "aws_lambda_function" "inference" {
  function_name = "${local.project_name}-inference"
  role          = aws_iam_role.lambda_exec_role.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.10"

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  timeout = 5
  memory_size = 128

  environment {
    variables = {
      LOG_LEVEL = "INFO"
    }
  }

  tags = local.tags
}

# API Gateway v2 HTTP API
resource "aws_apigatewayv2_api" "http_api" {
  name          = "${local.project_name}-http-api"
  protocol_type = "HTTP"
  tags          = local.tags
}

# Integración Lambda para HTTP API
resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id           = aws_apigatewayv2_api.http_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.inference.invoke_arn
  payload_format_version = "2.0"
}

# Ruta POST /infer
resource "aws_apigatewayv2_route" "post_infer" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /infer"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# Permiso para API Gateway invocar Lambda
resource "aws_lambda_permission" "allow_apigw_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.inference.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

# CloudWatch Log Group para Lambda (control explícito de retención)
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.inference.function_name}"
  retention_in_days = 14
  tags              = local.tags
}

# CloudWatch Log Group para Access Logs de API Gateway
resource "aws_cloudwatch_log_group" "apigw_access_logs" {
  name              = "/aws/apigateway/${local.project_name}-access"
  retention_in_days = 14
  tags              = local.tags
}

# Stage con Access Logs habilitados (default stage) para HTTP API
resource "aws_apigatewayv2_stage" "default_stage" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.apigw_access_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId",
      ip             = "$context.identity.sourceIp",
      requestTime    = "$context.requestTime",
      httpMethod     = "$context.httpMethod",
      routeKey       = "$context.routeKey",
      status         = "$context.status",
      protocol       = "$context.protocol",
      responseLength = "$context.responseLength",
      path           = "$context.path",
      integration    = "$context.integrationErrorMessage"
    })
  }

  tags = local.tags
}
