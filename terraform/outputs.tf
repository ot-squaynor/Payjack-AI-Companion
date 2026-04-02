output "api_url" {
  value = module.ecs.api_url
}

output "alb_dns_name" {
  value = module.ecs.alb_dns_name
}

output "processed_artifacts_bucket_name" {
  value = module.s3.processed_artifacts_bucket_name
}

output "kb_source_bucket_name" {
  value = module.s3.kb_source_bucket_name
}

output "kb_artifacts_bucket_name" {
  value = module.s3.kb_artifacts_bucket_name
}

output "frontend_bucket_name" {
  value = module.s3.frontend_bucket_name
}

output "external_transactions_bucket_name" {
  value = module.s3.external_transactions_bucket_name
}

output "external_accounts_bucket_name" {
  value = module.s3.external_accounts_bucket_name
}
