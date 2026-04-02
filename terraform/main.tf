locals {
  base_tags = merge(
    {
      Project     = var.app_name
      Environment = var.environment
      ManagedBy   = "terraform"
    },
    var.tags
  )

  force_destroy = var.allow_force_destroy || var.environment != "prod"

  container_image = "${var.ecr_repository_url}:${var.image_tag}"

  app_environment = merge(
    {
      APP_NAME                     = var.app_name
      APP_ENV                      = var.environment
      LOG_LEVEL                    = "INFO"
      CORS_ORIGINS                 = var.cors_origins
      PROCESSED_STORE_MODE         = "s3"
      PROCESSED_S3_PREFIX          = var.environment
      MANAGED_PROCESSED_PREFIX     = var.environment
      USE_MOCK_BEDROCK             = tostring(var.use_mock_bedrock)
      USE_LOCAL_RAG                = tostring(var.use_local_rag)
      ENABLE_DEBUG_TRACES          = tostring(var.enable_debug_traces)
      AWS_REGION                   = var.aws_region
      BEDROCK_MODEL_ID             = var.bedrock_model_id
      BEDROCK_EMBEDDING_MODEL_ID   = var.bedrock_embedding_model_id
      EXTERNAL_TRANSACTIONS_BUCKET = coalesce(var.external_transactions_bucket_name, "")
      EXTERNAL_TRANSACTIONS_PREFIX = var.external_transactions_prefix
      EXTERNAL_ACCOUNTS_BUCKET     = coalesce(var.external_accounts_bucket_name, "")
      EXTERNAL_ACCOUNTS_PREFIX     = var.external_accounts_prefix
    },
    var.extra_environment
  )
}

module "s3" {
  source = "./modules/s3"

  name_prefix                       = var.app_name
  environment                       = var.environment
  force_destroy                     = local.force_destroy
  create_frontend_bucket            = var.create_frontend_bucket
  shared_kb_source_bucket_name      = var.shared_kb_source_bucket_name
  shared_kb_artifacts_bucket_name   = var.shared_kb_artifacts_bucket_name
  external_transactions_bucket_name = var.external_transactions_bucket_name
  external_accounts_bucket_name     = var.external_accounts_bucket_name
  external_fees_bucket_name         = var.external_fees_bucket_name
  external_products_bucket_name     = var.external_products_bucket_name
  external_metadata_bucket_name     = var.external_metadata_bucket_name
  tags                              = local.base_tags
}

module "network" {
  source = "./modules/network"

  name_prefix             = var.app_name
  environment             = var.environment
  vpc_id                  = var.vpc_id
  alb_subnet_ids          = var.alb_subnet_ids
  ecs_subnet_ids          = var.ecs_subnet_ids
  alb_ingress_cidr_blocks = var.alb_ingress_cidr_blocks
  app_port                = var.app_port
  tags                    = local.base_tags
}

module "iam" {
  source = "./modules/iam"

  app_name    = var.app_name
  environment = var.environment
  external_bucket_arns = compact([
    module.s3.external_transactions_bucket_arn,
    module.s3.external_accounts_bucket_arn,
    module.s3.external_fees_bucket_arn,
    module.s3.external_products_bucket_arn,
    module.s3.external_metadata_bucket_arn
  ])
  managed_bucket_arns = compact([
    module.s3.processed_artifacts_bucket_arn,
    module.s3.kb_source_bucket_arn,
    module.s3.kb_artifacts_bucket_arn,
    module.s3.frontend_bucket_arn
  ])
  secret_arns = var.secret_arns
  tags        = local.base_tags
}

module "ecs" {
  source = "./modules/ecs"

  app_name                  = var.app_name
  environment               = var.environment
  aws_region                = var.aws_region
  vpc_id                    = var.vpc_id
  alb_subnet_ids            = var.alb_subnet_ids
  ecs_subnet_ids            = var.ecs_subnet_ids
  alb_security_group_id     = module.network.alb_security_group_id
  service_security_group_id = module.network.service_security_group_id
  execution_role_arn        = module.iam.execution_role_arn
  task_role_arn             = module.iam.task_role_arn
  container_image           = local.container_image
  app_port                  = var.app_port
  cpu                       = var.cpu
  memory                    = var.memory
  desired_count             = var.desired_count
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
  secret_arns = var.secret_arns
  tags        = local.base_tags
}
