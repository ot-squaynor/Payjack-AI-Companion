variable "app_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "archive_ttl_enabled" {
  description = "Enable DynamoDB TTL auto-purge of archived chat sessions via ttl_epoch_seconds."
  type        = bool
  default     = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
