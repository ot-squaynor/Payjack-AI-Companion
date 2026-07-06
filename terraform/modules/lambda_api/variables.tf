variable "app_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "image_uri" {
  type = string
}

variable "memory_size" {
  type = number
}

variable "timeout_seconds" {
  type = number
}

variable "architecture" {
  type = string
}

variable "environment_variables" {
  type    = map(string)
  default = {}
}

variable "external_bucket_arns" {
  type    = list(string)
  default = []
}

variable "managed_bucket_arns" {
  type    = list(string)
  default = []
}

variable "dynamodb_table_arns" {
  type    = list(string)
  default = []
}

variable "secret_arns" {
  type    = map(string)
  default = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}
