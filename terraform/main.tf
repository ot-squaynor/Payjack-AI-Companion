# Data source to get current AWS account ID
data "aws_caller_identity" "current" {}

locals {
  base_tags = merge(
    {
      Project     = var.app_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Runtime     = "lambda"
    },
    var.tags
  )

  force_destroy   = var.allow_force_destroy || var.environment != "prod"
  container_image = "${var.ecr_repository_url}:${var.image_tag}"

  external_transactions_bucket_name = var.external_transactions_bucket_name == null || trimspace(var.external_transactions_bucket_name) == "" ? null : var.external_transactions_bucket_name
  external_accounts_bucket_name     = var.external_accounts_bucket_name == null || trimspace(var.external_accounts_bucket_name) == "" ? null : var.external_accounts_bucket_name
  external_fees_bucket_name         = var.external_fees_bucket_name == null || trimspace(var.external_fees_bucket_name) == "" ? null : var.external_fees_bucket_name
  external_products_bucket_name     = var.external_products_bucket_name == null || trimspace(var.external_products_bucket_name) == "" ? null : var.external_products_bucket_name
  external_metadata_bucket_name     = var.external_metadata_bucket_name == null || trimspace(var.external_metadata_bucket_name) == "" ? null : var.external_metadata_bucket_name

  app_environment = merge(
    {
      APP_NAME                   = var.app_name
      APP_ENV                    = var.environment
      LOG_LEVEL                  = "INFO"
      CORS_ORIGINS               = var.cors_origins
      PROCESSED_STORE_MODE       = "s3"
      PROCESSED_S3_PREFIX        = var.environment
      MANAGED_PROCESSED_PREFIX   = var.environment
      USE_MOCK_BEDROCK           = tostring(var.use_mock_bedrock)
      USE_LOCAL_RAG              = tostring(var.use_local_rag)
      ENABLE_DEBUG_TRACES        = tostring(var.enable_debug_traces)
      BEDROCK_MODEL_ID           = var.bedrock_model_id
      BEDROCK_EMBEDDING_MODEL_ID = var.bedrock_embedding_model_id
      EXTERNAL_TRANSACTIONS_BUCKET = coalesce(
        local.external_transactions_bucket_name,
        ""
      )
      EXTERNAL_TRANSACTIONS_PREFIX = var.external_transactions_prefix
      EXTERNAL_ACCOUNTS_BUCKET = coalesce(
        local.external_accounts_bucket_name,
        ""
      )
      EXTERNAL_ACCOUNTS_PREFIX = var.external_accounts_prefix
    },
    var.extra_environment
  )
}

module "s3" {
  source = "./modules/s3"

  name_prefix                       = var.app_name
  environment                       = var.environment
  force_destroy                     = local.force_destroy
  create_frontend_bucket            = false
  shared_kb_source_bucket_name      = var.shared_kb_source_bucket_name
  shared_kb_artifacts_bucket_name   = var.shared_kb_artifacts_bucket_name
  external_transactions_bucket_name = local.external_transactions_bucket_name
  external_accounts_bucket_name     = local.external_accounts_bucket_name
  external_fees_bucket_name         = local.external_fees_bucket_name
  external_products_bucket_name     = local.external_products_bucket_name
  external_metadata_bucket_name     = local.external_metadata_bucket_name
  tags                              = local.base_tags
}

module "lambda_api" {
  source = "./modules/lambda_api"

  app_name        = var.app_name
  environment     = var.environment
  image_uri       = local.container_image
  memory_size     = var.lambda_memory_size
  timeout_seconds = var.lambda_timeout_seconds
  architecture    = var.lambda_architecture
  environment_variables = merge(
    local.app_environment,
    {
      PROCESSED_S3_BUCKET         = module.s3.processed_artifacts_bucket_name
      MANAGED_PROCESSED_BUCKET    = module.s3.processed_artifacts_bucket_name
      MANAGED_KB_SOURCE_BUCKET    = coalesce(module.s3.kb_source_bucket_name, "")
      MANAGED_KB_ARTIFACTS_BUCKET = coalesce(module.s3.kb_artifacts_bucket_name, "")
      KB_S3_BUCKET                = coalesce(module.s3.kb_artifacts_bucket_name, "")
      KB_S3_PREFIX                = "${var.environment}/processed_docs"
    }
  )
  external_bucket_arns = compact([
    module.s3.external_transactions_bucket_arn,
    module.s3.external_accounts_bucket_arn,
    module.s3.external_fees_bucket_arn,
    module.s3.external_products_bucket_arn,
    module.s3.external_metadata_bucket_arn,
  ])
  managed_bucket_arns = compact([
    module.s3.processed_artifacts_bucket_arn,
    module.s3.kb_source_bucket_arn,
    module.s3.kb_artifacts_bucket_arn,
  ])
  secret_arns = var.secret_arns
  tags        = local.base_tags
}

module "frontend" {
  source = "./modules/frontend_cloudfront"

  app_name        = var.app_name
  environment     = var.environment
  api_gateway_url = module.lambda_api.api_endpoint
  force_destroy   = local.force_destroy
  price_class     = var.cloudfront_price_class
  tags            = local.base_tags
}
