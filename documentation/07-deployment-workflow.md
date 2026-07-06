# Deployment Workflow

> **Question this diagram answers:** How does code get from a developer's machine to a running environment on AWS?

Deployment is fully automated through GitHub Actions. There are four distinct workflow files covering bootstrap, plan, deploy, and destroy. The active runtime path is Lambda + API Gateway + CloudFront — not ECS/Fargate.

---

## Deployment Phases

```mermaid
flowchart TD
    subgraph DEV ["👨‍💻 Developer"]
        GIT["Git push to GitHub"]
    end

    subgraph BOOTSTRAP ["🏗️ Bootstrap — run once\n.github/workflows/bootstrap-shared.yml"]
        B1["Terraform bootstrap stack\nterraform/bootstrap/"]
        B2["Terraform state S3 bucket\nDynamoDB lock table"]
        B3["ECR repository\nBackend container registry"]
        B4["Shared KB S3 buckets\nKB source + KB artifacts — persist across teardown"]
        B1 --> B2 & B3 & B4
    end

    subgraph PLAN ["📋 Plan — optional pre-check\n.github/workflows/plan-env.yml"]
        PL1["Backend tests"]
        PL2["Frontend tests"]
        PL3["Static Next.js build"]
        PL4["tf fmt · tf validate · tf plan"]
        PL1 & PL2 & PL3 --> PL4
    end

    subgraph DEPLOY ["🚀 Deploy — .github/workflows/deploy-env.yml"]
        D1["1. Backend + frontend tests"]
        D2["2. Build static Next.js export"]
        D3["3. Assume AWS role via GitHub OIDC"]
        D4["4. Validate external and shared buckets"]
        D5["5. Build + push Dockerfile.lambda → ECR"]
        D6["6. Terraform init + apply\nLambda · API Gateway · CloudFront · S3 frontend · DynamoDB chat tables · IAM"]
        D7["7. Publish processed datasets → managed S3 artifacts bucket"]
        D8["8. Sync frontend/out → private S3 frontend bucket"]
        D9["9. Invalidate CloudFront cache"]
        D10["10. Smoke tests\n/api/health · /api/ready · /api/chat · refusal · 404"]
        D11{{"Optional: publish_kb=true\nPublish KB artifacts → shared S3 KB artifacts bucket"}}
        D1 --> D2 --> D3 --> D4 --> D5 --> D6 --> D7 --> D11 --> D8 --> D9 --> D10
    end

    subgraph RUNTIME ["☁️ Live AWS Runtime"]
        CF["CloudFront CDN"]
        S3F["S3 Frontend bucket\nPrivate · OAC-protected"]
        APIGW["API Gateway\nHTTP API"]
        LAM["Lambda\nFastAPI container"]
        BED["Bedrock\nFoundation model"]
        S3A["S3 Artifacts bucket\nProcessed datasets + KB chunks"]
        DDBC["DynamoDB\nChat sessions + messages tables"]
        CW["CloudWatch\nLogs and metrics"]
    end

    GIT --> BOOTSTRAP
    GIT --> PLAN --> DEPLOY
    BOOTSTRAP --> DEPLOY

    D10 --> CF
    CF -->|"/* static"| S3F
    CF -->|"/api/* proxy"| APIGW --> LAM
    LAM --> BED & S3A & DDBC & CW
```

---

## Workflow Reference

| Workflow | File | Trigger | Purpose |
|---|---|---|---|
| Bootstrap | `bootstrap-shared.yml` | Manual — run once | Creates shared resources that outlive environments |
| Plan | `plan-env.yml` | Automatic on pull requests touching `backend/`, `frontend/`, `scripts/`, `terraform/`, or `.github/workflows/` — also manually dispatchable | Validates and plans environment changes |
| Deploy | `deploy-env.yml` | Manual — select `dev`, `test`, or `prod` | Full end-to-end deploy |
| Destroy | `destroy-env.yml` | Manual — requires typing `destroy-<environment>` to confirm | Destroys environment resources only |

---

## Environment Targets

```
dev | test | prod
```

Specify at workflow dispatch. Shared bootstrap resources and external raw-data buckets are never destroyed regardless of target.

---

## What the Destroy Workflow Protects

| Resource | Protected from destroy? |
|---|---|
| Terraform state bucket | Yes — bootstrap-managed |
| Shared KB source bucket | Yes — bootstrap-managed |
| Shared KB artifacts bucket | Yes — bootstrap-managed |
| ECR repository | Yes — bootstrap-managed |
| External raw-data buckets (`EXTERNAL_*`) | Yes — never managed by Terraform |
| Managed processed artifacts bucket | No — destroyed with environment |
| Frontend S3 bucket | No — emptied then destroyed |
| Chat history DynamoDB tables (sessions + messages) | No — destroyed with environment; not bootstrap-managed |

---

*Previous: [06 — Data Pipeline](06-data-pipeline.md) · Next: [08 — AWS Services](08-aws-services.md)*
