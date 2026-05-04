# Terraform Infrastructure Guide — Payjack AI Companion

This document describes every file in `terraform/`, explains what each one does based on its actual contents, and maps the progression from a blank AWS account to a running environment.

---

## Directory Structure

```text
terraform/
├── .terraform.lock.hcl            # Root provider lock — pins aws 6.41.0
├── bootstrap/                     # One-time shared resources (run once per account)
│   ├── .terraform.lock.hcl        # Bootstrap provider lock — pins aws 5.100.0
│   ├── main.tf                    # State bucket, DynamoDB lock, ECR, KB buckets
│   ├── variables.tf
│   ├── outputs.tf
│   ├── versions.tf
│   ├── backend-shared.hcl         # Remote backend pointer for bootstrap state
│   ├── local.tfvars               # Real account values for local bootstrap runs
│   └── terraform.tfvars.example   # Template with REPLACE_ME placeholders
├── modules/
│   ├── bedrock/                   # Empty placeholder — no .tf files yet
│   ├── kms/                       # Empty placeholder — no .tf files yet
│   ├── s3/                        # Bucket declarations — owned and external
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── lambda_api/                # Lambda function + API Gateway (active runtime)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── frontend_cloudfront/       # S3 bucket + CloudFront distribution (active frontend)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── iam/                       # ECS task IAM roles (retained, not active)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── ecs/                       # ECS Fargate cluster + ALB (retained, not active)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── network/                   # ALB and ECS security groups (retained, not active)
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── main.tf                        # Root environment orchestrator
├── variables.tf                   # All environment inputs
├── outputs.tf                     # Published resource identifiers
├── versions.tf                    # Provider and backend version pins
├── terraform.tfvars               # Intentionally non-binding — CI uses TF_VAR_* instead
├── terraform.tfvars.example       # Example values with 123456789012 placeholder account
└── local.dev.tfvars               # Real local dev values (ignored, machine-specific)
```

---

## Deployment Phases

There are three sequential phases. Each gates the next.

---

### Phase 1 — Bootstrap

**Folder:** `bootstrap/`
**Triggered by:** `.github/workflows/bootstrap-shared.yml`
**State location:** `bootstrap/shared/terraform.tfstate` in the state bucket itself

This is the foundation layer. It creates shared resources that must exist before anything else can be provisioned and that must never be destroyed by a normal environment teardown.

#### What it creates

| Resource | Name pattern | Notes |
|---|---|---|
| S3 state bucket | `var.tf_state_bucket_name` (required) | Versioned, AES-256 encrypted, all public access blocked |
| DynamoDB lock table | `var.tf_lock_table_name` (required) | PAY_PER_REQUEST, hash key `LockID` |
| ECR repository | `var.ecr_repository_name` (default: `payjack-ai-companion-backend`) | `MUTABLE` tags, scan on push enabled |
| S3 KB source bucket | `{project}-{account_id}-kb-source` unless overridden | Versioned, encrypted, `prevent_destroy = true` |
| S3 KB artifacts bucket | `{project}-{account_id}-kb-artifacts` unless overridden | Versioned, encrypted, `prevent_destroy = true` |
| S3 prefix markers | Six `aws_s3_object` resources inside `kb_source` | Creates empty keys for `raw_docs/`, `raw_docs/errors/`, `raw_docs/features/`, `raw_docs/fees/`, `raw_docs/help_center/`, `raw_docs/limits/` |

The KB bucket names default to `{project_slug}-{aws_account_id}-kb-source/artifacts` but can be overridden via `shared_kb_source_bucket_name` and `shared_kb_artifacts_bucket_name` variables. The `prevent_destroy = true` lifecycle rule means `terraform destroy` on any environment stack cannot touch these buckets.

The prefix markers pre-create the folder structure that `scripts/kb_build.py` writes into. Without them the KB pipeline would need to create keys against a bare bucket.

#### Bootstrap file details

**`bootstrap/versions.tf`**
- Terraform `>= 1.7.0`
- AWS provider `~> 5.95` — constraint resolves to `5.100.0` (pinned in `bootstrap/.terraform.lock.hcl`). One major version behind the environment stack (`~> 6.0` → `6.41.0`). This is intentional: bootstrap was established first and manages separate state
- `backend "s3" {}` — uses remote S3 backend, configured at init time via `backend-shared.hcl`
- No `provider "aws"` block — region must be supplied via `AWS_DEFAULT_REGION` environment variable or the GitHub Actions credentials step

**`bootstrap/backend-shared.hcl`**
```
bucket         = "payjack-ai-companion-tf-state-<account-id>-eu-west-2"
key            = "bootstrap/shared/terraform.tfstate"
region         = "eu-west-2"
dynamodb_table = "payjack-ai-companion-tf-locks"
```
Passed at init time: `terraform init -backend-config=backend-shared.hcl`

**`bootstrap/local.tfvars`**
Real account values for local bootstrap runs:
- Account: `<account-id>`, region: `eu-west-2`
- State bucket: `payjack-ai-companion-tf-state-<account-id>-eu-west-2`
- Lock table: `payjack-ai-companion-tf-locks`
- ECR: `payjack-ai-companion-backend`
- KB buckets: `payjack-ai-companion-<account-id>-kb-source/artifacts`

**`bootstrap/terraform.tfvars.example`**
Safe template with `REPLACE_ME` placeholders for the state bucket name and KB bucket names. New environments copy this and fill in their account-specific values.

**`bootstrap/outputs.tf`**
Exports: `tf_state_bucket_name`, `tf_lock_table_name`, `ecr_repository_url`, `kb_source_bucket_name`, `kb_source_bucket_arn`, `kb_artifacts_bucket_name`, `kb_artifacts_bucket_arn`.

---

### Phase 2 — External GitHub OIDC Role

The GitHub OIDC provider and GitHub Actions IAM role are now treated as external
account prerequisites, not Terraform resources managed by this repository.

This repository expects GitHub Actions to receive an `AWS_ROLE_ARN` secret for
each environment and uses `aws-actions/configure-aws-credentials@v4` to assume
that role during `bootstrap-shared.yml`, `plan-env.yml`, `deploy-env.yml`, and
`destroy-env.yml`.

That means there is no longer an `oidc-setup/` Terraform root in the repository
and no local OIDC Terraform state to maintain here. OIDC trust changes are
owned by the AWS/platform administrators who provision the role.

---

### Phase 3 — Environment Stack

**Root files:** `main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`
**Triggered by:** `.github/workflows/plan-env.yml` and `.github/workflows/deploy-env.yml`
**State location:** `env/{environment}/terraform.tfstate` in the bootstrap state bucket

This is the repeatable per-environment layer. It can be applied and destroyed freely without touching bootstrap or OIDC resources.

---

## Root Environment Files

### `main.tf`

Instantiates three modules and wires them together using a `locals` block.

**`locals` block responsibilities:**

1. **`base_tags`** — merges `Project`, `Environment`, `ManagedBy = "terraform"`, `Runtime = "lambda"` with any `var.tags`

2. **`force_destroy`** — `var.allow_force_destroy || var.environment != "prod"`. Non-prod environments always get `force_destroy = true` regardless of the input variable.

3. **`container_image`** — assembles `${var.ecr_repository_url}:${var.image_tag}`

4. **External bucket name guards** — five locals (`external_transactions_bucket_name`, etc.) normalise incoming values: if the variable is `null` or whitespace-only, the local is set to `null`. This prevents empty strings from being passed as bucket names.

5. **`app_environment`** — the Lambda environment variable map. Includes:
   - `APP_NAME`, `APP_ENV`, `LOG_LEVEL = "INFO"`, `CORS_ORIGINS`
   - `PROCESSED_STORE_MODE = "s3"`, `PROCESSED_S3_PREFIX = var.environment`
   - `MANAGED_PROCESSED_PREFIX = var.environment`
   - `USE_MOCK_BEDROCK`, `USE_LOCAL_RAG`, `ENABLE_DEBUG_TRACES`
   - `BEDROCK_MODEL_ID`, `BEDROCK_EMBEDDING_MODEL_ID`
   - `EXTERNAL_TRANSACTIONS_BUCKET`, `EXTERNAL_TRANSACTIONS_PREFIX`
   - `EXTERNAL_ACCOUNTS_BUCKET`, `EXTERNAL_ACCOUNTS_PREFIX`
   - Merged with `var.extra_environment` for any additional overrides
   - Note: fees, products, and metadata bucket names are passed to the s3 module for IAM ARN resolution but are **not** injected as Lambda environment variables in the current config

**Module calls:**

```
module "s3"       → ./modules/s3
module "lambda_api" → ./modules/lambda_api
module "frontend"   → ./modules/frontend_cloudfront
```

The Lambda module receives its full environment variable map by merging `local.app_environment` with four additional values resolved after the `s3` module runs:
- `PROCESSED_S3_BUCKET` and `MANAGED_PROCESSED_BUCKET` — both set to `module.s3.processed_artifacts_bucket_name`
- `MANAGED_KB_SOURCE_BUCKET` and `MANAGED_KB_ARTIFACTS_BUCKET` — from `module.s3.kb_source_bucket_name/artifacts_bucket_name`
- `KB_S3_BUCKET` — same as `kb_artifacts_bucket_name`
- `KB_S3_PREFIX` — `"${var.environment}/processed_docs"`

---

### `variables.tf`

All 27 input variables grouped by concern:

**Identity**
- `app_name` — default `payjack-ai-companion`, validated against `^[a-z0-9-]+$`
- `environment` — validated against `["dev", "test", "prod"]`
- `aws_region` — default `eu-west-2`

**Compute**
- `ecr_repository_url` — required, no default
- `image_tag` — required, no default
- `lambda_memory_size` — default `2048` MB
- `lambda_timeout_seconds` — default `60`
- `lambda_architecture` — default `x86_64`, validated against `["x86_64", "arm64"]`

**Frontend**
- `cloudfront_price_class` — default `PriceClass_100`

**Bucket lifecycle**
- `allow_force_destroy` — default `false`; combined with environment check in `main.tf`

**Shared KB buckets (from bootstrap outputs)**
- `shared_kb_source_bucket_name` — default `null`
- `shared_kb_artifacts_bucket_name` — default `null`

**External data buckets (five pairs — name + prefix)**
- `external_transactions_bucket_name` / `external_transactions_prefix`
- `external_accounts_bucket_name` / `external_accounts_prefix`
- `external_fees_bucket_name` / `external_fees_prefix`
- `external_products_bucket_name` / `external_products_prefix`
- `external_metadata_bucket_name` / `external_metadata_prefix`
All default to `null` / `""`. The prefix variables for fees, products, and metadata are defined but not currently wired into the Lambda env vars.

**AI configuration**
- `use_mock_bedrock` — default `false`
- `use_local_rag` — default `false`
- `enable_debug_traces` — default `true`
- `bedrock_model_id` — default `anthropic.claude-3-5-haiku-20241022-v1:0`
- `bedrock_embedding_model_id` — default `amazon.titan-embed-text-v2:0`
- `cors_origins` — default `http://localhost:3000`, injected as `CORS_ORIGINS`

**Injection escape hatches**
- `secret_arns` — `map(string)`, default `{}`, passed to lambda_api for Secrets Manager policy scoping
- `extra_environment` — `map(string)`, default `{}`, merged last into the Lambda env var map
- `tags` — `map(string)`, default `{}`, merged into `base_tags`

---

### `outputs.tf`

| Output | Source | Typical consumer |
|---|---|---|
| `api_url` | `module.lambda_api.api_endpoint` | `NEXT_PUBLIC_API_BASE_URL` env var, smoke tests |
| `api_gateway_id` | `module.lambda_api.api_id` | Debugging, CloudWatch |
| `lambda_function_name` | `module.lambda_api.lambda_function_name` | Manual invocations |
| `cloudfront_url` | `"https://${module.frontend.cloudfront_domain_name}"` | End-user access point, E2E test base URL |
| `cloudfront_distribution_id` | `module.frontend.cloudfront_distribution_id` | Cache invalidation step in deploy workflow |
| `frontend_bucket_name` | `module.frontend.frontend_bucket_name` | `aws s3 sync` step for static asset upload |
| `processed_artifacts_bucket_name` | `module.s3.processed_artifacts_bucket_name` | Artifact publish step |
| `kb_source_bucket_name` | `module.s3.kb_source_bucket_name` | KB upload step |
| `kb_artifacts_bucket_name` | `module.s3.kb_artifacts_bucket_name` | KB artifact publish step |
| `external_transactions_bucket_name` | `module.s3.external_transactions_bucket_name` | Verification logging |
| `external_accounts_bucket_name` | `module.s3.external_accounts_bucket_name` | Verification logging |

---

### `versions.tf`

```hcl
terraform >= 1.7.0
aws provider ~> 6.0   # resolves to 6.41.0 (pinned in .terraform.lock.hcl)
backend "s3" {}       # configured at init time via -backend-config flags
provider "aws" { region = var.aws_region }
```

The S3 backend is intentionally left empty here. The backend bucket, key, region, and DynamoDB table are passed via `-backend-config` at `terraform init` time, which lets the same code serve `dev`, `test`, and `prod` environments without modification.

---

### `terraform.tfvars`

This file is **intentionally non-binding**. Every value is commented out. The comment at the top reads:

> This file is intentionally non-binding so GitHub Actions can supply runtime values through TF_VAR_* environment variables.

In CI, all variable values flow in as `TF_VAR_*` environment variables set by the workflow. For local applies, the developer either exports `TF_VAR_*` values manually or uses `local.dev.tfvars`.

---

### `terraform.tfvars.example`

A committed, safe example file using placeholder account `123456789012` and demo bucket names. Contains uncommented key-value pairs that can be copied into a local, uncommitted `.tfvars` file. Covers: environment, app_name, region, ECR URL, image tag, KB bucket names, two external bucket names, and the four AI/debug toggles.

---

### `local.dev.tfvars`

The actual local development config. Contains machine-specific values for the current AWS account in `eu-west-2`:
- Real ECR URL
- Real KB bucket names matching bootstrap outputs
- `allow_force_destroy = true`
- `use_mock_bedrock = false`, `use_local_rag = false`, `enable_debug_traces = true`
- `bedrock_model_id = "amazon.nova-micro-v1:0"` (Nova Micro, not the default Claude Haiku)
- `bedrock_embedding_model_id = "amazon.titan-embed-text-v2:0"`
- `cors_origins = "http://localhost:3000"`

Used with: `terraform plan -var-file="local.dev.tfvars"`

---

## Module Reference

### `modules/s3/`

**Role:** Declares every S3 relationship for the environment — buckets this stack owns outright, and external buckets owned by other systems that need to be referenced for IAM.

**Bucket naming:** The `processed_artifacts` bucket is named `{app_name}-{environment}-{account_id}-processed`. The account ID is included so the name is globally unique without any random suffix.

**What it creates:**
- `aws_s3_bucket.processed_artifacts` — runtime home for Parquet and manifest files produced by `scripts/dataset_transform.py`. Versioned, AES-256 encrypted, all public access blocked.
- `aws_s3_bucket.frontend` — created only if `create_frontend_bucket = true`. In the current root `main.tf` this is set to `false`, so this bucket is never created by this module. The frontend bucket is owned by the `frontend_cloudfront` module instead.

**What it looks up (data sources, not created):**
- `data.aws_s3_bucket.external_transactions` — conditional on bucket name being non-null
- `data.aws_s3_bucket.external_accounts` — conditional
- `data.aws_s3_bucket.external_fees` — conditional
- `data.aws_s3_bucket.external_products` — conditional
- `data.aws_s3_bucket.external_metadata` — conditional
- `data.aws_s3_bucket.shared_kb_source` — conditional on KB bucket name being non-null
- `data.aws_s3_bucket.shared_kb_artifacts` — conditional

All five external bucket data sources use `count = var.xxx == null ? 0 : 1` so no lookup is attempted if the variable is null. This allows the stack to be applied in environments where some external buckets do not yet exist.

**Outputs:** The KB bucket outputs (`kb_source_bucket_name`, `kb_source_bucket_arn`, etc.) pass through the input variables and data source ARNs respectively — the module does not create KB buckets.

---

### `modules/lambda_api/`

**Role:** The active compute and API layer. Deploys FastAPI as a container image on Lambda, fronted by API Gateway HTTP API v2.

**What it creates:**

| Resource | Detail |
|---|---|
| `aws_cloudwatch_log_group.lambda` | `/aws/lambda/{name}-api`, 14-day retention |
| `aws_cloudwatch_log_group.api` | `/aws/apigateway/{name}-api`, 14-day retention |
| `aws_iam_role.lambda` | Assume role for `lambda.amazonaws.com` |
| `aws_iam_policy.lambda` | Assembled from dynamic statements (see below) |
| `aws_iam_role_policy_attachment.lambda` | Attaches the policy to the role |
| `aws_lambda_function.api` | `Image` package type, configurable memory/timeout/architecture |
| `aws_apigatewayv2_api.this` | HTTP protocol, named `{name}-http-api` |
| `aws_apigatewayv2_integration.lambda` | `AWS_PROXY`, payload format `2.0`, **30-second integration timeout** |
| `aws_apigatewayv2_route.default` | `$default` route — catches all paths |
| `aws_apigatewayv2_stage.default` | `$default` stage, `auto_deploy = true`, structured JSON access logging |
| `aws_lambda_permission.api_gateway` | Allows API GW to invoke the function |

**IAM policy statements (all dynamic — only added when relevant inputs are non-empty):**

| Sid | Actions | Resources | Condition |
|---|---|---|---|
| `WriteLambdaLogs` | `logs:CreateLogStream`, `logs:PutLogEvents` | Lambda log group stream ARN | Always present |
| `ReadExternalBuckets` | `s3:GetObject`, `s3:ListBucket` | External bucket ARNs + `/*` | Only if external ARNs are provided |
| `ReadManagedBuckets` | `s3:GetObject`, `s3:ListBucket` | Managed bucket ARNs + `/*` | Only if managed ARNs are provided |
| `InvokeBedrockModels` | `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream` | `*` | Always present |
| `ReadSecrets` | `secretsmanager:GetSecretValue` | Values from `var.secret_arns` | Only if secret ARNs are provided |

The managed buckets (processed artifacts, KB source, KB artifacts) are **read-only** from the Lambda function's perspective — `s3:GetObject` and `s3:ListBucket` only, no `PutObject`. Artifact publishing is done by the GitHub Actions role, not the Lambda function.

**Integration timeout note:** API Gateway has a 30-second timeout (`timeout_milliseconds = 30000`) while the Lambda function timeout is 60 seconds. API Gateway will time out before Lambda does on long-running requests.

**Outputs:** `api_endpoint`, `api_id`, `lambda_function_name`, `lambda_function_arn`

---

### `modules/frontend_cloudfront/`

**Role:** Delivers the Next.js static frontend via CloudFront and routes all `/api/*` traffic to the backend API Gateway.

**Bucket naming:** `{app_name}-{environment}-{account_id}-frontend` (account ID included for global uniqueness).

**What it creates:**

| Resource | Detail |
|---|---|
| `aws_s3_bucket.frontend` | Private, versioned, AES-256 encrypted, all public access blocked |
| `aws_cloudfront_origin_access_control.frontend` | SigV4 signing, `s3` origin type, `always` signing behavior |
| `aws_cloudfront_distribution.frontend` | Two origins: S3 frontend + API Gateway |
| S3 bucket policy | Restricts `s3:GetObject` to the CloudFront service principal scoped to this distribution's ARN |

**CloudFront distribution configuration:**
- `default_root_object = "index.html"`
- `is_ipv6_enabled = true`
- No geo restrictions
- Default SSL certificate (CloudFront-generated domain, no custom domain)
- `price_class` is configurable (default `PriceClass_100` from root variables)

**Cache behaviors:**

| Behavior | Path | Origin | Methods | Cache policy |
|---|---|---|---|---|
| Default | All paths | S3 frontend | `GET`, `HEAD`, `OPTIONS` | `658327ea-...` (Managed-CachingOptimized) — aggressively caches static assets |
| Ordered | `/api/*` | API Gateway | All seven HTTP methods | `4135ea2d-...` (Managed-CachingDisabled) — no caching; also applies origin request policy `b689b0a8-...` (Managed-AllViewerExceptHostHeader) |

**Custom error responses:**
- HTTP 403 → serve `index.html` with status 200
- HTTP 404 → serve `index.html` with status 200

These two rules enable SPA client-side routing. When CloudFront cannot find a path in S3 (returns 403 via OAC), it falls back to `index.html` and the Next.js router handles the path in the browser.

**Outputs:** `frontend_bucket_name`, `frontend_bucket_arn`, `cloudfront_distribution_id`, `cloudfront_domain_name`

---

### `modules/bedrock/` — Empty placeholder

Directory exists with no `.tf` files. Reserved for a future Bedrock-managed Knowledge Base or Bedrock Guardrails module. Currently the Bedrock integration is handled entirely through IAM policy statements in `lambda_api` (granting `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`) and environment variables (`BEDROCK_MODEL_ID`, `BEDROCK_EMBEDDING_MODEL_ID`). When a managed KB or Guardrails resource is needed, this is where that module will live.

---

### `modules/kms/` — Empty placeholder

Directory exists with no `.tf` files. Reserved for a future customer-managed KMS key module. Currently all buckets use SSE-S3 (AES-256, AWS-managed keys). If the project moves to customer-managed CMKs for stricter key rotation control or cross-account access, the key and key policy resources would be defined here and referenced from `modules/s3/`.

---

### `modules/iam/` — Retained, not active

**Role:** IAM execution and task roles for ECS Fargate deployment.

Not called from the root `main.tf`. Retained for the ECS deployment path. Creates two roles:
- **Execution role** — for the ECS agent (pulls the image, writes logs). Attaches `AmazonECSTaskExecutionRolePolicy`.
- **Task role** — for application code. Grants `s3:GetObject` + `s3:ListBucket` on external and managed buckets, `bedrock:InvokeModel` + `bedrock:InvokeModelWithResponseStream`, and `secretsmanager:GetSecretValue` on named secrets.

**Outputs:** `execution_role_arn`, `task_role_arn`

---

### `modules/ecs/` — Retained, not active

**Role:** ECS Fargate cluster with ALB, task definition, and service.

Not called from the root `main.tf`. Retained for the ECS deployment path. Creates: CloudWatch log group, ECS cluster, ALB, target group (IP-based, `/health` health check), HTTP listener on port 80, ECS task definition (Fargate, `awsvpc` networking), and ECS service.

**Outputs:** `api_url` (ALB DNS with `http://` prefix), `alb_dns_name`, `cluster_name`, `service_name`

---

### `modules/network/` — Retained, not active

**Role:** Security groups for the ALB and ECS service when running on ECS.

Not called from the root `main.tf`. Creates:
- ALB security group — ingress on port 80 from configurable CIDR blocks (iterated with `for_each`), all egress
- Service security group — ingress from the ALB security group on `var.app_port`, all egress

**Outputs:** `alb_security_group_id`, `service_security_group_id`

---

## How the Pieces Connect

```text
GitHub Actions (deploy-env.yml)
│
├── 1. Assumes externally provisioned GitHub Actions role
│
├── 2. docker build + push → ECR (created by bootstrap)
│
├── 3. terraform init -backend-config=...
│       Reads state from bootstrap S3 bucket
│
├── 4. terraform apply
│       module "s3"
│         ├── Creates: processed_artifacts bucket
│         └── Looks up: external buckets + shared KB buckets (data sources)
│       module "lambda_api"
│         ├── Creates: CloudWatch log groups, IAM role+policy, Lambda function, API GW
│         └── Receives: full env var map including resolved bucket names
│       module "frontend"
│         ├── Creates: frontend S3 bucket, CloudFront OAC, CloudFront distribution
│         └── Receives: API Gateway endpoint URL (to set as origin)
│
├── 5. aws s3 sync frontend/out/ → frontend_bucket_name
│
├── 6. CloudFront invalidation (/*) — clears cached static assets
│
├── 7. aws s3 sync backend/data/processed/ → processed_artifacts_bucket
│
└── 8. (Optional) aws s3 sync backend/kb/ → KB source + artifacts buckets
```

---

## State Isolation

| Stack | State key | Managed by |
|---|---|---|
| Bootstrap | `bootstrap/shared/terraform.tfstate` | `bootstrap-shared.yml` |
| Dev environment | `env/dev/terraform.tfstate` | `deploy-env.yml` |
| Test environment | `env/test/terraform.tfstate` | `deploy-env.yml` |
| Prod environment | `env/prod/terraform.tfstate` | `deploy-env.yml` |

A `terraform destroy` on the dev environment destroys only what the dev state tracks. The bootstrap resources (state bucket, ECR, KB buckets) are in a separate state file and are also protected by `prevent_destroy`. They are never touched by environment teardown.

---

## Security Properties

| Property | Implementation |
|---|---|
| No stored AWS credentials | OIDC role assumed per-job by GitHub Actions |
| All buckets private | `block_public_acls`, `block_public_policy`, `ignore_public_acls`, `restrict_public_buckets = true` on every bucket |
| Encryption at rest | AES-256 SSE on every bucket |
| Versioning | State bucket, KB buckets, processed artifacts bucket, frontend bucket |
| Frontend restricted to CloudFront | S3 bucket policy allows `s3:GetObject` only from the CloudFront service principal scoped to this distribution's ARN via OAC |
| Lambda reads external data only | External bucket IAM is `s3:GetObject` + `s3:ListBucket` only — no write |
| Lambda reads managed buckets only | Managed bucket IAM is also read-only — artifact publishing is the GitHub Actions role's job |
| Secrets via Secrets Manager | `secret_arns` map generates a scoped `secretsmanager:GetSecretValue` policy statement; no secrets in `.tfvars` |
| Concurrent state safety | DynamoDB lock table prevents two Terraform runs from corrupting state simultaneously |

---

## Key Design Decisions

**`terraform.tfvars` is intentionally empty**
CI supplies all values via `TF_VAR_*` environment variables. The committed file documents what variables exist without hardcoding values. Local developers use `local.dev.tfvars` directly.

**Lambda over ECS as the active path**
Lambda removes the need for a VPC, NAT Gateway, ALB, cluster, and service definition. FastAPI runs identically under `uvicorn` locally and under `Mangum` (ASGI adapter) on Lambda. ECS modules are retained but inactive.

**Single CloudFront distribution for frontend and API**
Routing `/api/*` through CloudFront to API Gateway means frontend and backend share one domain, eliminating CORS complexity. The API Gateway URL is stripped of `https://` and used as a custom origin in the CloudFront distribution.

**External buckets as data sources**
Financial data buckets (transactions, accounts, fees, products, metadata) are owned by systems outside this stack. Referencing them as `data "aws_s3_bucket"` sources resolves their ARNs for IAM policy generation without Terraform claiming any ownership over them.

**Bootstrap/environment split**
Shared resources live in a separate Terraform root module with its own state and `prevent_destroy` on critical buckets. Environment resources are freely teardown-able.

**Bedrock model ID as a variable**
Model selection (`amazon.nova-micro-v1:0` in dev) is a Lambda environment variable, not baked into the container. Changing the model requires only `terraform apply` — no image rebuild.

**API Gateway timeout shorter than Lambda timeout**
The API Gateway integration timeout is 30 seconds while the Lambda function timeout is 60 seconds. This is a deliberate choice: API Gateway will return a timeout error to the client before the Lambda function itself times out, which provides a cleaner failure mode for the user while the Lambda continues executing in the background.
