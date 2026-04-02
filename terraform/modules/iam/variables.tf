variable "app_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "external_bucket_arns" {
  type    = list(string)
  default = []
}

variable "managed_bucket_arns" {
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
