output "processed_artifacts_bucket_name" {
  value = aws_s3_bucket.processed_artifacts.bucket
}

output "processed_artifacts_bucket_arn" {
  value = aws_s3_bucket.processed_artifacts.arn
}

output "kb_source_bucket_name" {
  value = var.shared_kb_source_bucket_name
}

output "kb_source_bucket_arn" {
  value = var.shared_kb_source_bucket_name == null ? null : data.aws_s3_bucket.shared_kb_source[0].arn
}

output "kb_artifacts_bucket_name" {
  value = var.shared_kb_artifacts_bucket_name
}

output "kb_artifacts_bucket_arn" {
  value = var.shared_kb_artifacts_bucket_name == null ? null : data.aws_s3_bucket.shared_kb_artifacts[0].arn
}

output "frontend_bucket_name" {
  value = var.create_frontend_bucket ? aws_s3_bucket.frontend[0].bucket : null
}

output "frontend_bucket_arn" {
  value = var.create_frontend_bucket ? aws_s3_bucket.frontend[0].arn : null
}

output "external_transactions_bucket_name" {
  value = var.external_transactions_bucket_name
}

output "external_transactions_bucket_arn" {
  value = var.external_transactions_bucket_name == null ? null : data.aws_s3_bucket.external_transactions[0].arn
}

output "external_accounts_bucket_name" {
  value = var.external_accounts_bucket_name
}

output "external_accounts_bucket_arn" {
  value = var.external_accounts_bucket_name == null ? null : data.aws_s3_bucket.external_accounts[0].arn
}

output "external_fees_bucket_arn" {
  value = var.external_fees_bucket_name == null ? null : data.aws_s3_bucket.external_fees[0].arn
}

output "external_products_bucket_arn" {
  value = var.external_products_bucket_name == null ? null : data.aws_s3_bucket.external_products[0].arn
}

output "external_metadata_bucket_arn" {
  value = var.external_metadata_bucket_name == null ? null : data.aws_s3_bucket.external_metadata[0].arn
}
