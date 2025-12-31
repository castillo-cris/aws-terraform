############################################
# outputs.tf
############################################

output "lambda_function_arn" {
  value       = aws_lambda_function.inference.arn
  description = "ARN de la Lambda de inferencia"
}

output "http_api_endpoint" {
  value       = aws_apigatewayv2_api.http_api.api_endpoint
  description = "Endpoint base de la HTTP API (usar POST /infer)"
}