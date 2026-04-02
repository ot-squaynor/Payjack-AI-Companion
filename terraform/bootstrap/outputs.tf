output "tf_state_bucket_name" {
  value = aws_s3_bucket.tf_state.bucket
}

output "tf_lock_table_name" {
  value = aws_dynamodb_table.tf_lock.name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "kb_source_bucket_name" {
  value = aws_s3_bucket.kb_source.bucket
}

output "kb_source_bucket_arn" {
  value = aws_s3_bucket.kb_source.arn
}

output "kb_artifacts_bucket_name" {
  value = aws_s3_bucket.kb_artifacts.bucket
}

output "kb_artifacts_bucket_arn" {
  value = aws_s3_bucket.kb_artifacts.arn
}
