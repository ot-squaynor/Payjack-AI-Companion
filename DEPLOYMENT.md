# Deployment

This project currently deploys through GitHub Actions, Terraform, Docker, AWS
Lambda, API Gateway, S3, and CloudFront.

The active public runtime path is:

```text
GitHub Actions
  -> backend Lambda image in ECR
  -> Terraform environment stack
  -> Lambda + API Gateway
  -> static Next.js export in S3
  -> CloudFront frontend with /api/* routed to API Gateway
```

The ECS/Fargate Terraform modules remain in the repository as optional historical
infrastructure, but they are not the active deploy path.

## Chat Response Routing

Each chat request is classified by the orchestrator and handled by one of the following routes:

| Route | Code name | Grounding mode | LLM called |
|-------|-----------|----------------|------------|
| Tools | `deterministic_tool_route` | `tool` | Yes — tool output injected into prompt |
| RAG | `rag_route` | `rag` | Yes — retrieved KB chunks injected into prompt |
| Hybrid | `hybrid_route` | `hybrid` | Yes — both tool output and KB chunks injected |
| LLM Direct | `safe_general_route` | `base` | Yes — no tools, no retrieval, system prompt only |
| Clarification | `clarification_route` | — | No — static question returned |
| Refusal | `refusal_route` | — | No — static refusal message returned |

The `USE_MOCK_BEDROCK` environment variable controls whether LLM calls go to Amazon Bedrock or to the local mock adapter. It applies equally to all four LLM routes. `BEDROCK_MODEL_ID` selects the foundation model used for all routes.

## Required AWS/GitHub Setup

Use the externally provisioned GitHub Actions role, then configure the GitHub
environment used by the workflows.

Required GitHub environment secret:

```text
AWS_ROLE_ARN
```

Required or commonly used GitHub environment variables:

```text
AWS_REGION
APP_NAME
TF_STATE_BUCKET
TF_LOCK_TABLE
ECR_REPOSITORY_NAME
SHARED_KB_SOURCE_BUCKET
SHARED_KB_ARTIFACTS_BUCKET
EXTERNAL_TRANSACTIONS_BUCKET
EXTERNAL_TRANSACTIONS_PREFIX
EXTERNAL_ACCOUNTS_BUCKET
EXTERNAL_ACCOUNTS_PREFIX
EXTERNAL_FEES_BUCKET
EXTERNAL_FEES_PREFIX
EXTERNAL_PRODUCTS_BUCKET
EXTERNAL_PRODUCTS_PREFIX
EXTERNAL_METADATA_BUCKET
EXTERNAL_METADATA_PREFIX
USE_MOCK_BEDROCK
USE_LOCAL_RAG
ENABLE_DEBUG_TRACES
BEDROCK_MODEL_ID
BEDROCK_EMBEDDING_MODEL_ID
CORS_ORIGINS
```

Only `TF_STATE_BUCKET`, `TF_LOCK_TABLE`, and `AWS_ROLE_ARN` are hard blockers for
the shared bootstrap flow. The environment deploy also needs a transactions
source bucket if processed datasets should be built from S3 during deployment.

## One-Time Bootstrap

Run this workflow manually from GitHub Actions:

```text
.github/workflows/bootstrap-shared.yml
```

Use `apply_changes=true`.

This creates the shared resources that should outlive normal environment
teardown:

```text
Terraform state bucket
Terraform lock table
Backend ECR repository
Shared KB source bucket
Shared KB artifacts bucket
```

The bootstrap stack lives in `terraform/bootstrap`.

## Plan An Environment

Run this workflow before a deployment:

```text
.github/workflows/plan-env.yml
```

Choose one of:

```text
dev
test
prod
```

The plan workflow runs backend tests, frontend tests, the static frontend build,
Terraform formatting, Terraform validation, and Terraform plan.

## Deploy An Environment

Run this workflow manually:

```text
.github/workflows/deploy-env.yml
```

Inputs:

```text
environment: dev | test | prod
image_tag: optional image tag override
publish_kb: true | false
```

The deploy workflow performs these steps:

```text
1. Check out the repo.
2. Install Python, Node.js, and Terraform.
3. Run backend unit/tool/integration tests.
4. Run frontend tests.
5. Build the static Next.js frontend with NEXT_PUBLIC_API_BASE_URL=/api.
6. Assume the AWS role via GitHub OIDC.
7. Resolve ECR and Terraform runtime variables.
8. Validate configured external/shared buckets.
9. Build and push Dockerfile.lambda to ECR.
10. Run Terraform init and apply in terraform/.
11. Build and publish processed datasets to the managed S3 bucket.
12. Optionally build and publish KB artifacts.
13. Sync frontend/out to the private frontend S3 bucket.
14. Invalidate CloudFront.
15. Smoke test /api/health, /api/ready, /api/chat, refusal behavior, and an API 404 JSON response.
```

The deployed URL is the `cloudfront_url` Terraform output.

## Destroy An Environment

Run this workflow manually:

```text
.github/workflows/destroy-env.yml
```

Set `confirmation` to:

```text
destroy-dev
destroy-test
destroy-prod
```

For non-production environments, the workflow empties the managed frontend and
processed-artifact buckets before running Terraform destroy. Shared bootstrap
resources and external raw-data buckets are intentionally not part of normal
environment teardown.

External tool-pipeline buckets are never destroy targets. This includes:

```text
EXTERNAL_TRANSACTIONS_BUCKET
EXTERNAL_ACCOUNTS_BUCKET
EXTERNAL_FEES_BUCKET
EXTERNAL_PRODUCTS_BUCKET
EXTERNAL_METADATA_BUCKET
```

The destroy workflow checks that managed bucket outputs do not match any of
those external bucket names before it empties managed environment buckets.

## Local Terraform Applies

The scripts in `scripts/deploy.ps1` and `scripts/deploy.sh` are partial
Terraform helpers. They do not build or push the backend image, publish the
frontend, publish datasets, publish KB artifacts, invalidate CloudFront, or run
smoke tests.

Use them only when an image already exists in ECR and the required environment
variables are exported:

```text
TF_STATE_BUCKET
TF_LOCK_TABLE
TF_VAR_ecr_repository_url or ECR_REPOSITORY_URL
TF_VAR_app_name
TF_VAR_aws_region
```

For normal deployments, prefer the GitHub Actions workflow.

## Local Files And Git Hygiene

Keep real local deployment values out of Git. Use ignored files such as:

```text
terraform/local.dev.tfvars
terraform/bootstrap/local.tfvars
terraform/bootstrap/backend-shared.hcl
.env
```

The checked-in `terraform/terraform.tfvars` is intentionally non-binding and
contains commented examples only.

Terraform provider lock files can be committed deliberately when you want
reproducible provider selection for a stack:

```text
terraform/.terraform.lock.hcl
terraform/bootstrap/.terraform.lock.hcl
```

## Docker Image Hygiene

The root `.dockerignore` keeps local secrets, Python environments, frontend
dependencies/build outputs, tests, Terraform files, local datasets, and generated
KB artifacts out of the backend image build context.

The deployed backend image is built from:

```text
Dockerfile.lambda
```

The deployed Lambda runtime reads processed datasets and KB chunks from S3, not
from local generated artifacts inside the image.
