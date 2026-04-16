variable "app_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "api_gateway_url" {
  type = string
}

variable "force_destroy" {
  type = bool
}

variable "price_class" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
