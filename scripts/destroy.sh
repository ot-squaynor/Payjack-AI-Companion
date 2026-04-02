#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-dev}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TERRAFORM_ROOT="${PROJECT_ROOT}/terraform"

: "${TF_STATE_BUCKET:?TF_STATE_BUCKET must be set before running destroy.sh.}"
: "${TF_LOCK_TABLE:?TF_LOCK_TABLE must be set before running destroy.sh.}"

if [[ -z "${TF_VAR_ecr_repository_url:-}" ]]; then
  : "${ECR_REPOSITORY_URL:?TF_VAR_ecr_repository_url or ECR_REPOSITORY_URL must be set before running destroy.sh.}"
  export TF_VAR_ecr_repository_url="${ECR_REPOSITORY_URL}"
fi

export TF_VAR_app_name="${TF_VAR_app_name:-payjack-ai-companion}"
export TF_VAR_aws_region="${TF_VAR_aws_region:-${AWS_REGION:-us-east-1}}"
export TF_VAR_environment="${ENVIRONMENT}"
export TF_VAR_image_tag="destroy-local"

cd "${TERRAFORM_ROOT}"
terraform init \
  -backend-config="bucket=${TF_STATE_BUCKET}" \
  -backend-config="key=environments/${ENVIRONMENT}/terraform.tfstate" \
  -backend-config="region=${TF_VAR_aws_region}" \
  -backend-config="dynamodb_table=${TF_LOCK_TABLE}"
terraform destroy -auto-approve
