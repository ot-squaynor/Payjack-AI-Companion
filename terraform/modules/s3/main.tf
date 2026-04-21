data "aws_caller_identity" "current" {}

locals {
  bucket_prefix = lower(replace("${var.name_prefix}-${var.environment}-${data.aws_caller_identity.current.account_id}", "_", "-"))
}

# External tool-pipeline buckets are read-only data sources. Terraform must
# never create, empty, or destroy transaction/account/source-data buckets here.
data "aws_s3_bucket" "external_transactions" {
  count  = var.external_transactions_bucket_name == null ? 0 : 1
  bucket = var.external_transactions_bucket_name
}

data "aws_s3_bucket" "external_accounts" {
  count  = var.external_accounts_bucket_name == null ? 0 : 1
  bucket = var.external_accounts_bucket_name
}

data "aws_s3_bucket" "external_fees" {
  count  = var.external_fees_bucket_name == null ? 0 : 1
  bucket = var.external_fees_bucket_name
}

data "aws_s3_bucket" "external_products" {
  count  = var.external_products_bucket_name == null ? 0 : 1
  bucket = var.external_products_bucket_name
}

data "aws_s3_bucket" "external_metadata" {
  count  = var.external_metadata_bucket_name == null ? 0 : 1
  bucket = var.external_metadata_bucket_name
}

data "aws_s3_bucket" "shared_kb_source" {
  count  = var.shared_kb_source_bucket_name == null ? 0 : 1
  bucket = var.shared_kb_source_bucket_name
}

data "aws_s3_bucket" "shared_kb_artifacts" {
  count  = var.shared_kb_artifacts_bucket_name == null ? 0 : 1
  bucket = var.shared_kb_artifacts_bucket_name
}

resource "aws_s3_bucket" "processed_artifacts" {
  bucket        = "${local.bucket_prefix}-processed"
  force_destroy = var.force_destroy
  tags          = var.tags
}

resource "aws_s3_bucket" "frontend" {
  count         = var.create_frontend_bucket ? 1 : 0
  bucket        = "${local.bucket_prefix}-frontend"
  force_destroy = var.force_destroy
  tags          = var.tags
}

resource "aws_s3_bucket_versioning" "processed_artifacts" {
  bucket = aws_s3_bucket.processed_artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "frontend" {
  count  = var.create_frontend_bucket ? 1 : 0
  bucket = aws_s3_bucket.frontend[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "processed_artifacts" {
  bucket = aws_s3_bucket.processed_artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  count  = var.create_frontend_bucket ? 1 : 0
  bucket = aws_s3_bucket.frontend[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "processed_artifacts" {
  bucket = aws_s3_bucket.processed_artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  count  = var.create_frontend_bucket ? 1 : 0
  bucket = aws_s3_bucket.frontend[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
