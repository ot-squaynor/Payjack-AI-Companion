locals {
  base_tags = merge(
    {
      Project   = var.project_name
      ManagedBy = "terraform"
      Scope     = "shared"
    },
    var.tags
  )
}

resource "aws_s3_bucket" "tf_state" {
  bucket = var.tf_state_bucket_name
  tags   = local.base_tags
}

resource "aws_s3_bucket_versioning" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "tf_lock" {
  name         = var.tf_lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"
  tags         = local.base_tags

  attribute {
    name = "LockID"
    type = "S"
  }
}

resource "aws_ecr_repository" "backend" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "MUTABLE"
  tags                 = local.base_tags

  image_scanning_configuration {
    scan_on_push = true
  }
}
