variable "name_prefix" {
  type = string
}

variable "environment" {
  type = string
}

variable "force_destroy" {
  type = bool
}

variable "create_frontend_bucket" {
  type = bool
}

variable "shared_kb_source_bucket_name" {
  type    = string
  default = null
}

variable "shared_kb_artifacts_bucket_name" {
  type    = string
  default = null
}

variable "external_transactions_bucket_name" {
  description = "Existing read-only transactions bucket. This module must never create, empty, or destroy it."
  type        = string
  default     = null
}

variable "external_accounts_bucket_name" {
  description = "Existing read-only accounts bucket. This module must never create, empty, or destroy it."
  type        = string
  default     = null
}

variable "external_fees_bucket_name" {
  description = "Existing read-only fees/limits bucket. This module must never create, empty, or destroy it."
  type        = string
  default     = null
}

variable "external_products_bucket_name" {
  description = "Existing read-only products bucket. This module must never create, empty, or destroy it."
  type        = string
  default     = null
}

variable "external_metadata_bucket_name" {
  description = "Existing read-only metadata bucket. This module must never create, empty, or destroy it."
  type        = string
  default     = null
}

variable "tags" {
  type    = map(string)
  default = {}
}
