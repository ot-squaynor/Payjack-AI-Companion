output "tf_state_bucket_name" {
  value = aws_s3_bucket.tf_state.bucket
}

output "tf_lock_table_name" {
  value = aws_dynamodb_table.tf_lock.name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}
