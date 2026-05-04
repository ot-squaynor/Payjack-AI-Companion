output "api_gateway_url" {
  description = "URL of the API Gateway"
  value = module.lambda_api.api_endpoint
}

output "api_gateway_id" {
  value = module.lambda_api.api_id
}

output "lambda_function_name" {
  value = module.lambda_api.lambda_function_name
}

output "cloudfront_url" {
  description = "URL of the CloudFront distribution"
  value = "https://${module.frontend.cloudfront_domain_name}"
}

output "cloudfront_distribution_id" {
  value = module.frontend.cloudfront_distribution_id
}

output "frontend_bucket_name" {
  description = "Name of the S3 bucket for frontend"
  value = module.frontend.frontend_bucket_name
}

output "processed_artifacts_bucket_name" {
  description = "Name of the S3 bucket for processed artifacts"
  value = module.s3.processed_artifacts_bucket_name
}

output "kb_source_bucket_name" {
  description = "Name of the S3 bucket for the RAG knowledgebase"
  value = module.s3.kb_source_bucket_name
}

output "kb_artifacts_bucket_name" {
  description = "Name of the S3 bucket for unprocessed artifacts"
  value = module.s3.kb_artifacts_bucket_name
}

output "external_transactions_bucket_name" {
  description = "Name of the S3 bucket for transactions"
  value = module.s3.external_transactions_bucket_name
}

output "external_accounts_bucket_name" {
  description = "Name of the S3 bucket for accounts"
  value = module.s3.external_accounts_bucket_name
}
