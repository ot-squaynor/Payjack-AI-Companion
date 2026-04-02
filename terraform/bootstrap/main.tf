data "aws_caller_identity" "current" {}

locals {
  base_tags = merge(
    {
      Project   = var.project_name
      ManagedBy = "terraform"
      Scope     = "shared"
    },
    var.tags
  )

  project_slug = lower(replace(var.project_name, "_", "-"))
  kb_source_bucket_name = lower(
    replace(
      coalesce(
        var.shared_kb_source_bucket_name,
        "${local.project_slug}-${data.aws_caller_identity.current.account_id}-kb-source"
      ),
      "_",
      "-"
    )
  )
  kb_artifacts_bucket_name = lower(
    replace(
      coalesce(
        var.shared_kb_artifacts_bucket_name,
        "${local.project_slug}-${data.aws_caller_identity.current.account_id}-kb-artifacts"
      ),
      "_",
      "-"
    )
  )
  kb_source_prefixes = toset(
    [
      "raw_docs",
      "raw_docs/errors",
      "raw_docs/features",
      "raw_docs/fees",
      "raw_docs/help_center",
      "raw_docs/limits",
    ]
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

resource "aws_s3_bucket" "kb_source" {
  bucket = local.kb_source_bucket_name
  tags   = local.base_tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "kb_source" {
  bucket = aws_s3_bucket.kb_source.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "kb_source" {
  bucket = aws_s3_bucket.kb_source.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "kb_source" {
  bucket = aws_s3_bucket.kb_source.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "kb_source_prefix_markers" {
  for_each = local.kb_source_prefixes

  bucket  = aws_s3_bucket.kb_source.id
  key     = "${each.value}/"
  content = ""
}

resource "aws_s3_bucket" "kb_artifacts" {
  bucket = local.kb_artifacts_bucket_name
  tags   = local.base_tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "kb_artifacts" {
  bucket = aws_s3_bucket.kb_artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "kb_artifacts" {
  bucket = aws_s3_bucket.kb_artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "kb_artifacts" {
  bucket = aws_s3_bucket.kb_artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
