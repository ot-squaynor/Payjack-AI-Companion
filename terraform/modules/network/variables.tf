variable "name_prefix" {
  type = string
}

variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "alb_subnet_ids" {
  type = list(string)
}

variable "ecs_subnet_ids" {
  type = list(string)
}

variable "alb_ingress_cidr_blocks" {
  type = list(string)
}

variable "app_port" {
  type = number
}

variable "tags" {
  type    = map(string)
  default = {}
}
