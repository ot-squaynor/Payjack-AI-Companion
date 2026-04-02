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

variable "external_transactions_bucket_name" {
  type    = string
  default = null
}

variable "external_accounts_bucket_name" {
  type    = string
  default = null
}

variable "external_fees_bucket_name" {
  type    = string
  default = null
}

variable "external_products_bucket_name" {
  type    = string
  default = null
}

variable "external_metadata_bucket_name" {
  type    = string
  default = null
}

variable "tags" {
  type    = map(string)
  default = {}
}
