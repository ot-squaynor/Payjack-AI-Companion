environment = "dev"
app_name    = "payjack-ai-companion"

# Fill these values per environment before applying locally, or supply them
# through GitHub Actions environment variables and -var flags.
vpc_id         = "vpc-REPLACE_ME"
alb_subnet_ids = ["subnet-REPLACE_ME_A", "subnet-REPLACE_ME_B"]
ecs_subnet_ids = ["subnet-REPLACE_ME_A", "subnet-REPLACE_ME_B"]

ecr_repository_url = "REPLACE_ME.dkr.ecr.us-east-1.amazonaws.com/payjack-ai-companion-backend"
image_tag          = "latest"

shared_kb_source_bucket_name    = "REPLACE_ME_SHARED_KB_SOURCE_BUCKET"
shared_kb_artifacts_bucket_name = "REPLACE_ME_SHARED_KB_ARTIFACTS_BUCKET"

external_transactions_bucket_name = "REPLACE_ME_TRANSACTIONS_BUCKET"
external_accounts_bucket_name     = "REPLACE_ME_ACCOUNTS_BUCKET"
