variable "app_name" {
  type    = string
  default = "payjack-ai-companion"
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
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
  type    = list(string)
  default = ["0.0.0.0/0"]
}

variable "app_port" {
  type    = number
  default = 8000
}

variable "ecr_repository_url" {
  type = string
}

variable "image_tag" {
  type = string
}

variable "cpu" {
  type    = number
  default = 512
}

variable "memory" {
  type    = number
  default = 1024
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "allow_force_destroy" {
  type    = bool
  default = false
}

variable "create_frontend_bucket" {
  type    = bool
  default = false
}

variable "external_transactions_bucket_name" {
  type    = string
  default = null
}

variable "external_transactions_prefix" {
  type    = string
  default = ""
}

variable "external_accounts_bucket_name" {
  type    = string
  default = null
}

variable "external_accounts_prefix" {
  type    = string
  default = ""
}

variable "external_fees_bucket_name" {
  type    = string
  default = null
}

variable "external_fees_prefix" {
  type    = string
  default = ""
}

variable "external_products_bucket_name" {
  type    = string
  default = null
}

variable "external_products_prefix" {
  type    = string
  default = ""
}

variable "external_metadata_bucket_name" {
  type    = string
  default = null
}

variable "external_metadata_prefix" {
  type    = string
  default = ""
}

variable "use_mock_bedrock" {
  type    = bool
  default = true
}

variable "use_local_rag" {
  type    = bool
  default = false
}

variable "enable_debug_traces" {
  type    = bool
  default = true
}

variable "bedrock_model_id" {
  type    = string
  default = "anthropic.claude-3-5-haiku-20241022-v1:0"
}

variable "bedrock_embedding_model_id" {
  type    = string
  default = "amazon.titan-embed-text-v2:0"
}

variable "cors_origins" {
  type    = string
  default = "http://localhost:3000"
}

variable "secret_arns" {
  type    = map(string)
  default = {}
}

variable "extra_environment" {
  type    = map(string)
  default = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}
