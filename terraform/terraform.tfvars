# This file is intentionally non-binding so GitHub Actions can supply runtime
# values through TF_VAR_* environment variables.
#
# For local applies, either export TF_VAR_* values or copy the examples below
# into a local, uncommitted tfvars file.
#
# app_name           = "payjack-ai-companion"
# environment        = "dev"
# aws_region         = "eu-west-2"
# ecr_repository_url = "509399591563.dkr.ecr.eu-west-2.amazonaws.com/payjack-ai-companion-backend"
# image_tag          = "latest"
#
# shared_kb_source_bucket_name    = "payjack-ai-companion-509399591563-kb-source"
# shared_kb_artifacts_bucket_name = "payjack-ai-companion-509399591563-kb-artifacts"
#
# external_transactions_bucket_name = "payjack-ai-demo-transactions-509399591563-eu-west-2-an"
# external_transactions_prefix      = ""
# external_accounts_bucket_name     = "payjack-demo-accounts"
# external_accounts_prefix          = ""
#
# use_mock_bedrock    = false
# use_local_rag       = false
# enable_debug_traces = true
# allow_force_destroy = true
