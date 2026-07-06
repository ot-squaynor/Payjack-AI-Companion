locals {
  name_prefix = "${var.app_name}-${var.environment}"
}

resource "aws_dynamodb_table" "chat_sessions" {
  name         = "${local.name_prefix}-chat-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  tags         = var.tags

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "owner_key"
    type = "S"
  }

  attribute {
    name = "updated_at"
    type = "S"
  }

  global_secondary_index {
    name            = "gsi_owner_recency"
    hash_key        = "owner_key"
    range_key       = "updated_at"
    projection_type = "ALL"
  }

  dynamic "ttl" {
    for_each = var.archive_ttl_enabled ? [1] : []
    content {
      attribute_name = "ttl_epoch_seconds"
      enabled        = true
    }
  }

  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_dynamodb_table" "chat_messages" {
  name         = "${local.name_prefix}-chat-messages"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  range_key    = "sort_key"
  tags         = var.tags

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "sort_key"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }
}
