# Payjack-AI-Companion
Read-only, transaction-led AI financial companion for Payjack

**Project Overview & System Summary**

---

## 1. What This Project Is

The Payjack AI Financial Companion is a **read-only, AI-powered advisory layer** embedded inside the Payjack app.

It helps users:

- Understand their transactions
- Interpret spending patterns
- Clarify balance changes
- Navigate app features
- Understand fees, limits, and product mechanics

It does **not**:
- Send money
- Modify accounts
- Provide financial advice
- Open products
- Perform credit assessment

The system is designed to be:

- Secure
- PCI-DSS aligned
- ISO27001 aligned
- RAG-grounded for documentation and policy/help content
- Tool-led for structured financial interpretation
- Agent-enabled for routing between tools and documentation
- Deployable inside OrangeTech's AWS infrastructure

---

## 2. High-Level Architecture

The system has three primary intelligence layers:

1. **Tools Layer (Structured Data Access)**
2. **RAG Layer (Knowledge Retrieval)**
3. **LLM Generation Layer (Natural Language Responses)**

These are coordinated by an **AI Orchestrator**.

### Current Runtime Flow

```text
Next.js Chat Interface
  -> FastAPI API
  -> Orchestrator
  -> (Deterministic Tools and/or RAG Retriever)
  -> Bedrock or Mock Model Adapter
  -> Response Formatter
  -> Structured Output to User
```

### Infrastructure Flow

```text
GitHub Actions
  -> Shared Bootstrap Terraform
  -> ECR + Shared KB Buckets + Terraform State
  -> Environment Terraform
  -> ECS + ALB + IAM + S3
  -> Backend Runtime and Managed Artifacts
```

---

## 3. How It Works (End-to-End)

### Step 1: User Asks a Question

Examples:
- "How much did I spend on food last month?"
- "Why is my transfer still pending?"
- "How do I split a bill?"

---

### Step 2: Intent Classification

The orchestrator determines:

- Transaction question -> use Tools
- Feature explanation -> use RAG
- Mixed -> use both
- Disallowed (advice/execution) -> refuse safely

---

### Step 3A: Tools (Structured Financial Data)

The system calls read-only internal functions:

- Transaction lookup
- Spend summary
- Recurring detection
- Status explanation
- Product balances (where available)

These return **structured JSON** and remain deterministic.

---

### Step 3B: RAG (Knowledge Retrieval)

If explanation is required:

1. Query the Knowledge Base
2. Retrieve top relevant document chunks
3. Filter by metadata
4. Pass retrieved context to the model layer

This ensures:
- Policy answers are grounded
- Fees, limits, and help content are citeable
- Structured customer data is never retrieved via RAG

---

### Step 4: LLM Generation

The system sends:

- User message
- Tool outputs (if any)
- Retrieved RAG context (if any)
- System guardrails

to a **Bedrock foundation model** in AWS, or to a local mock adapter during local-first development.

The model generates:
- Structured conversational responses
- Tables where needed
- Step-by-step guidance

---

### Step 5: Safety Layer

Before returning output:

- PII masking is applied
- Policy guard checks run
- Audit logging is captured
- Telemetry is recorded

---

## 4. How It Works With AWS

The repository is AWS-native, but it supports a local-first developer workflow before real AWS wiring is required.

### Core Services and Integration Status

| Layer | Current Service / Pattern | Status |
|-------|---------------------------|--------|
| LLM generation | Amazon Bedrock via `boto3` | Current |
| Local model seam | Mock Bedrock adapter | Current |
| Documentation retrieval | Local/file retriever and shared S3-backed KB artifacts | Current |
| Structured financial data | Processed artifacts loaded from local disk or S3 | Current |
| Compute | ECS (containerized FastAPI service) | Current |
| Container registry | Amazon ECR | Current |
| Secrets / configuration | IAM + env vars + Terraform wiring | Current |
| Logging / metrics hooks | CloudWatch-oriented runtime + telemetry modules | Current |
| Documentation buckets | Shared S3 KB source and artifacts buckets | Current |
| CDN for frontend | CloudFront | Optional future seam |
| Event-driven functions | AWS Lambda | Optional future seam |
| Managed Bedrock Knowledge Base resources | Possible later addition | Optional future seam |
| Datadog | Additional observability option | Optional future seam |

### Deployment Model

- Code -> GitHub
- CI/CD -> GitHub Actions
- Container -> Docker -> ECR
- Infrastructure -> Terraform
- Runtime Deploy -> ECS + ALB
- Storage -> S3

The active repo path is **GitHub Actions + Terraform + Docker + ECS**, not TeamCity or Ansible AWX.

---

## 5. Current Repository Status and Integrations

| Capability | Current status | Implemented location | Notes |
|------------|----------------|----------------------|-------|
| Deterministic financial tools | Implemented | `backend/app/tools/` | Tool-first vertical slice is in place |
| Structured data pipeline | Implemented | `backend/app/data_pipeline/`, `scripts/dataset_transform.py` | Produces processed artifacts, QC, and manifest sidecars |
| Processed artifact repository layer | Implemented | `backend/app/repository/` | Loads local or S3-backed processed datasets |
| Orchestration | Implemented | `backend/app/orchestrator/` | Routes between tool, RAG, clarify, and refusal paths |
| Bedrock client abstraction | Implemented | `backend/app/llm/` | Supports mock mode for local testing |
| RAG retrieval | Partially implemented | `backend/app/rag/`, `backend/kb/`, `scripts/kb_*.py` | Local/file path is ready; managed Bedrock KB remains optional |
| Backend API | Implemented | `backend/app/api/`, `backend/app/main.py` | FastAPI `/health`, `/ready`, and `/chat` |
| Next.js frontend | Implemented | `frontend/app/`, `frontend/components/`, `frontend/lib/` | Chat UI plus debug route |
| Frontend tests | Implemented | `frontend/*.config.ts`, `frontend/e2e/`, `frontend/tests/` | Vitest + Playwright |
| Backend tests | Implemented | `backend/tests/` | Unit, integration, rag, llm, red-team, tool tests |
| Docker backend runtime | Implemented | `backend/Dockerfile` | Python 3.12 slim + Uvicorn |
| Terraform bootstrap/env split | Implemented | `terraform/bootstrap/`, `terraform/` | Shared bootstrap plus environment stack |
| GitHub Actions workflows | Implemented | `.github/workflows/` | Bootstrap, plan, deploy, destroy |
| Shared KB buckets | Implemented | `terraform/bootstrap/main.tf` | Create-once shared KB source and KB artifacts buckets |
| CloudFront | Not currently implemented | N/A | Optional future path for frontend hosting |
| Lambda | Not currently implemented | N/A | Optional future path for async/event-driven extensions |

---

## 6. Why the File Structure Is Designed This Way

The repository is structured by **system responsibility**, not by technology.

### Core Principles

1. **Separation of concerns**
2. **LLM abstraction layer**
3. **Data isolation**
4. **Security isolation**
5. **Scalability readiness**

### Folder Logic

#### `/backend/app`
Runtime application code deployed to ECS.

Separated into:
- `api/` -> HTTP layer
- `data_pipeline/` -> offline artifact creation and validation
- `llm/` -> model abstraction and prompts
- `orchestrator/` -> reasoning and workflow logic
- `rag/` -> retrieval logic
- `repository/` -> processed artifact loading
- `security/` -> compliance logic
- `telemetry/` -> logging, metrics, and cost tracking
- `tools/` -> deterministic financial logic

#### `/backend/data`
Structured financial datasets and runtime artifacts.

- `raw/` -> source exports
- `processed/` -> canonical artifacts used by the repository layer
- `mock/` -> fixture-style data
- `embeddings/` -> optional local vector persistence

#### `/backend/kb`
Knowledge Base content and generated documentation artifacts.

- `raw_docs/` -> source markdown/docs for RAG
- `processed_docs/` -> chunked docs and embeddings sidecars
- `metadata/` -> KB manifests and related metadata

#### `/frontend`
Next.js user interface layer.

- `app/` -> routes and pages
- `components/` -> chat UI building blocks
- `lib/` -> typed frontend contracts and API client
- `e2e/` -> Playwright tests

#### `/scripts`
Operational entrypoints for data processing, KB preparation, and Terraform wrappers.

#### `/terraform`
Infrastructure as Code for AWS.

- `bootstrap/` -> shared create-once resources
- `modules/` -> reusable environment modules
- root stack -> environment-specific ECS/networking/runtime configuration

#### `/.github/workflows`
Automation for bootstrap, plan, deploy, and destroy flows.

---

## 7. Curated Repository Tree

```text
payjack-ai-companion/
|-- .github/
|   `-- workflows/
|       |-- bootstrap-shared.yml
|       |-- deploy-env.yml
|       |-- destroy-env.yml
|       `-- plan-env.yml
|-- backend/
|   |-- app/
|   |   |-- api/
|   |   |-- data_pipeline/
|   |   |-- llm/
|   |   |-- orchestrator/
|   |   |-- rag/
|   |   |-- repository/
|   |   |-- security/
|   |   |-- telemetry/
|   |   `-- tools/
|   |-- data/
|   |   |-- embeddings/
|   |   |-- mock/
|   |   |-- processed/
|   |   `-- raw/
|   |-- kb/
|   |   |-- metadata/
|   |   |-- processed_docs/
|   |   `-- raw_docs/
|   |-- tests/
|   |   |-- evaluation/
|   |   |-- fixtures/
|   |   |-- integration/
|   |   |-- llm_tests/
|   |   |-- rag_tests/
|   |   |-- red_team_tests/
|   |   |-- tool_tests/
|   |   `-- unit/
|   |-- Dockerfile
|   |-- requirements.dev.txt
|   |-- requirements.runtime.txt
|   `-- .env.example
|-- frontend/
|   |-- app/
|   |-- components/
|   |-- e2e/
|   |-- lib/
|   |-- tests/
|   |-- package.json
|   |-- playwright.config.ts
|   `-- vitest.config.ts
|-- memory/
|-- prototype/
|-- scripts/
|-- terraform/
|   |-- bootstrap/
|   |-- modules/
|   |-- main.tf
|   |-- outputs.tf
|   |-- variables.tf
|   `-- versions.tf
|-- payjack_folder_strategy.md
`-- README.md
```

Generated and local-only directories such as `.venv`, `.next`, `node_modules`, `coverage`, `.pytest_tmp`, `__pycache__`, and `.terraform` are intentionally excluded from this architectural view.

---

## 8. Data Pipelines

There are two main pipelines.

### A. Financial Data Pipeline

Raw transaction and account data ->
ingestion ->
normalization ->
category mapping ->
recurring enrichment ->
quality checks ->
processed artifact persistence

Outputs include:
- `*.parquet`
- `manifest.json`
- `qc_report.json`
- `pipeline_summary.json`

This is **non-predictive**, read-only, and descriptive.

### B. RAG Pipeline

Documentation ->
markdown cleaning ->
metadata tagging ->
chunking ->
embedding ->
retrieval artifacts in local files or shared S3 KB storage

This pipeline ensures retrieval accuracy while keeping customer financial data out of RAG.

---

## 9. Agents and Orchestration

The system behaves like a controlled, lightweight agent.

It can:

- Classify intent
- Call tools
- Retrieve documents
- Merge structured and unstructured context
- Generate grounded responses

Agent logic includes:

- Tool allowlists
- Clarification handling
- Refusal handling
- Audit logging

This keeps the assistant controlled, not autonomous.

---

## 10. Security, Compliance, and Observability

The system is built with:

- Read-only architecture
- Least-privilege IAM
- Encryption at rest and in transit
- PII masking before model calls
- Audit logs for tool usage
- Guardrails against execution and advice
- Telemetry hooks for latency, error, retrieval, and cost tracking

This aligns with:

- PCI-DSS style secure data handling
- ISO 27001 style access control and monitoring

CloudWatch-oriented observability is the current default path in the repository. Datadog can be added later if needed.

---

## 11. Local Setup

The recommended local path is:

- Python 3.12 for the backend
- Node 20+ for the frontend
- local processed artifacts
- local KB artifacts
- mock Bedrock enabled

### Runtime Entrypoints and Config Sources

- Local backend entrypoint: `backend/app/main.py`
- Backend container entrypoint: `backend/Dockerfile`
- Frontend local entrypoint: `frontend/app/page.tsx`
- Frontend debug route: `frontend/app/debug/page.tsx`
- Local backend configuration template: `backend/.env.example`
- Local backend secrets/config source: auto-loaded `backend/.env`
- Shared infrastructure bootstrap source of truth: `terraform/bootstrap/main.tf`
- Environment infrastructure source of truth: `terraform/main.tf`
- Deployment automation source of truth: `.github/workflows/`

### PowerShell

```powershell
cd C:\Users\Nii Quaynor\projects\Payjack-AI-Companion

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.dev.txt

python scripts\dataset_transform.py --source-mode local --local-root backend\data\raw --output-dir backend\data\processed --environment local
python scripts\kb_build.py
python scripts\embeddings_generate.py

python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Open a second PowerShell window for the frontend:

```powershell
cd C:\Users\Nii Quaynor\projects\Payjack-AI-Companion\frontend

npm install
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"
$env:NEXT_PUBLIC_DEFAULT_USER_ID = "dev-user"
$env:NEXT_PUBLIC_DEFAULT_TENANT_ID = "dev-tenant"
$env:NEXT_PUBLIC_DEFAULT_ACCOUNT_IDS = "acc-001"

npm run dev
```

### CMD

```cmd
cd C:\Users\Nii Quaynor\projects\Payjack-AI-Companion

py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.dev.txt

python scripts\dataset_transform.py --source-mode local --local-root backend\data\raw --output-dir backend\data\processed --environment local
python scripts\kb_build.py
python scripts\embeddings_generate.py

python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

In a second CMD window:

```cmd
cd C:\Users\Nii Quaynor\projects\Payjack-AI-Companion\frontend

npm install
set NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
set NEXT_PUBLIC_DEFAULT_USER_ID=dev-user
set NEXT_PUBLIC_DEFAULT_TENANT_ID=dev-tenant
set NEXT_PUBLIC_DEFAULT_ACCOUNT_IDS=acc-001

npm run dev
```

Local backend configuration is sourced from `backend/.env.example` and the auto-loaded local `backend/.env`.

---

## 12. Testing

### Backend Tests

```powershell
cd C:\Users\Nii Quaynor\projects\Payjack-AI-Companion
.\.venv\Scripts\Activate.ps1

python -m pytest backend\tests\unit backend\tests\tool_tests backend\tests\integration backend\tests\rag_tests backend\tests\llm_tests backend\tests\red_team_tests -q
python -m pytest backend\tests\unit backend\tests\tool_tests backend\tests\integration backend\tests\rag_tests backend\tests\llm_tests backend\tests\red_team_tests --cov=backend\app --cov-report=term-missing -q
```

### Frontend Tests

```powershell
cd C:\Users\Nii Quaynor\projects\Payjack-AI-Companion\frontend

npm test
npm run test:coverage
npm run test:e2e
npm run build
```

Test stack in the repository:

- Backend: `pytest`, `pytest-cov`
- Frontend: `Vitest`, `Testing Library`, `Playwright`

---

## 13. Docker

The backend ships with a container definition in `backend/Dockerfile`.

### Build

```powershell
cd C:\Users\Nii Quaynor\projects\Payjack-AI-Companion
docker build -f backend/Dockerfile -t payjack-backend .
```

### Run

```powershell
cd C:\Users\Nii Quaynor\projects\Payjack-AI-Companion
docker run --rm -p 8000:8000 --env-file backend/.env payjack-backend
```

For local-only mode, processed artifacts should already exist under `backend/data/processed` before building and running the image. If the runtime is configured for S3-backed processed artifacts instead, local artifact generation is not required.

---

## 14. GitHub Actions and Terraform

### Shared Bootstrap Resources

The shared bootstrap stack creates resources that should exist once and not be destroyed with normal environment teardown:

- Terraform state bucket
- Terraform lock table
- Shared ECR repository
- Shared KB source bucket
- Shared KB artifacts bucket

This is managed by:

- `.github/workflows/bootstrap-shared.yml`
- `terraform/bootstrap/main.tf`

### Environment Resources

The environment stack manages deployable runtime infrastructure:

- ECS cluster/service/task definition
- ALB and target groups
- IAM wiring
- Managed processed-artifacts bucket
- Optional frontend bucket
- Network/security groups

This is managed by:

- `.github/workflows/plan-env.yml`
- `.github/workflows/deploy-env.yml`
- `.github/workflows/destroy-env.yml`
- `terraform/main.tf`

### Workflow Summary

| Workflow | Purpose |
|----------|---------|
| `bootstrap-shared.yml` | Creates and protects shared bootstrap resources |
| `plan-env.yml` | Validates and plans environment infrastructure |
| `deploy-env.yml` | Tests, builds, pushes, applies Terraform, publishes processed artifacts, and optionally publishes KB artifacts |
| `destroy-env.yml` | Destroys environment-managed resources only, leaving shared KB buckets and external raw buckets intact |

---

## 15. Known Non-Implemented or Future Extensions

The following are valid integration directions, but they are **not currently implemented as first-class repo infrastructure**:

- **AWS Lambda**: no current runtime module, workflow, or deployment path in the repository
- **CloudFront**: no current distribution module; an optional frontend bucket pattern exists, but CDN hosting is still a future extension
- **Managed Bedrock Knowledge Base resources**: the repo currently supports local/shared KB artifact flows and can later add a Bedrock-managed KB if required
- **Datadog**: not the current default observability path

These are intentionally documented as future seams rather than current capabilities.

---

## 16. Summary

The Payjack AI Financial Companion is:

- A secure, read-only AI interpretation layer
- Powered by Bedrock with a local mock seam for development
- Grounded using RAG for documentation and policy/help content
- Structured using deterministic financial tools
- Orchestrated through a controlled workflow engine
- Deployable on ECS through GitHub Actions, Terraform, and Docker
- Designed for compliance and auditability from day one

It transforms raw transaction history into understandable financial insight without ever touching execution systems.
