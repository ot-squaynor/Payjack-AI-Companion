variable "project_name" {
  description = "Name prefix for all resources."
  type        = string
  default     = "payjack-ai-companion"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "App name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Deployment environment name."
  type        = string

  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "Environment must be one of dev, test, or prod."
  }
}

variable "aws_region" {
  description = "AWS region for regional resources."
  type        = string
  default     = "eu-west-2"
}

variable "ecr_repository_url" {
  description = "ECR repository URL that stores the backend Lambda image."
  type        = string
}

variable "image_tag" {
  description = "Backend image tag to deploy."
  type        = string
}

variable "lambda_memory_size" {
  description = "Lambda memory size in MB."
  type        = number
  default     = 2048
}

variable "lambda_timeout_seconds" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 60
}

variable "lambda_architecture" {
  description = "Lambda instruction set architecture."
  type        = string
  default     = "x86_64"

  validation {
    condition     = contains(["x86_64", "arm64"], var.lambda_architecture)
    error_message = "Lambda architecture must be x86_64 or arm64."
  }
}

variable "cloudfront_price_class" {
  description = "CloudFront edge location price class."
  type        = string
  default     = "PriceClass_100"
}

variable "allow_force_destroy" {
  description = "Allow Terraform to force-destroy non-prod buckets."
  type        = bool
  default     = false
}

variable "shared_kb_source_bucket_name" {
  description = "Shared KB source bucket created by bootstrap."
  type        = string
  default     = null
}

variable "shared_kb_artifacts_bucket_name" {
  description = "Shared KB artifacts bucket created by bootstrap."
  type        = string
  default     = null
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
  default = false
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
