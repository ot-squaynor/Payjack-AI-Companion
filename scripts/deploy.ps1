param(
    [string]$Environment = "dev",
    [string]$ImageTag = "local"
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$terraformRoot = Join-Path $projectRoot "terraform"

if (-not $env:TF_STATE_BUCKET) {
    throw "TF_STATE_BUCKET must be set before running deploy.ps1."
}

if (-not $env:TF_LOCK_TABLE) {
    throw "TF_LOCK_TABLE must be set before running deploy.ps1."
}

if (-not $env:TF_VAR_ecr_repository_url) {
    if ($env:ECR_REPOSITORY_URL) {
        $env:TF_VAR_ecr_repository_url = $env:ECR_REPOSITORY_URL
    } else {
        throw "TF_VAR_ecr_repository_url or ECR_REPOSITORY_URL must be set before running deploy.ps1."
    }
}

if (-not $env:TF_VAR_app_name) {
    $env:TF_VAR_app_name = "payjack-ai-companion"
}

if (-not $env:TF_VAR_aws_region) {
    $env:TF_VAR_aws_region = if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" }
}

$env:TF_VAR_environment = $Environment
$env:TF_VAR_image_tag = $ImageTag

Push-Location $terraformRoot
try {
    terraform init `
        -backend-config="bucket=$($env:TF_STATE_BUCKET)" `
        -backend-config="key=environments/$Environment/terraform.tfstate" `
        -backend-config="region=$($env:TF_VAR_aws_region)" `
        -backend-config="dynamodb_table=$($env:TF_LOCK_TABLE)"

    terraform apply -auto-approve
}
finally {
    Pop-Location
}
