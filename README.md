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

These are coordinated by an **AI Orchestrator** that classifies each message and selects one of four response routes:

| Route | Code name | When used |
|-------|-----------|-----------|
| **Tools** | `deterministic_tool_route` | User asks about their own transactions, spending, balances, or recurring charges |
| **RAG** | `rag_route` | User asks about Payjack documentation, fees, limits, policies, or features |
| **Hybrid** | `hybrid_route` | User asks a question that needs both personal financial data and policy context |
| **LLM Direct** | `safe_general_route` | User asks a safe, general question that does not require personal data or documentation lookup — answered by the LLM alone without any grounding |

Static non-LLM paths also exist for `clarification_route` (vague requests) and `refusal_route` (disallowed requests). These return a fixed answer without calling the model.

### Current Runtime Flow

```text
Next.js Chat Interface
  -> FastAPI API
  -> Orchestrator (intent classification + route selection)
  -> [Tools route]   Deterministic financial tool call(s)  -> LLM
  -> [RAG route]     Knowledge Base retrieval              -> LLM
  -> [Hybrid route]  Tools + Knowledge Base retrieval      -> LLM
  -> [LLM Direct]    (no tools, no retrieval)              -> LLM
  -> [Static]        Clarification or refusal answer (no LLM call)
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
  -> Lambda + API Gateway + CloudFront + S3
  -> Public Frontend, Backend Runtime, and Managed Artifacts
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

The orchestrator classifies the message and picks a route:

- Transaction / spend / balance / recurring question with personal anchor -> **Tools route**
- Payjack documentation, fees, limits, policy, or product question -> **RAG route**
- Personal data question that also needs policy context -> **Hybrid route**
- Safe conversational or general question (no personal data, no docs needed) -> **LLM Direct route**
- Vague or ambiguous message -> **Clarification** (static, no LLM call)
- Disallowed request (advice, execution, PII extraction) -> **Refusal** (static, no LLM call)

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

### Step 3C: LLM Direct (No Grounding)

For safe general questions that do not need personal data or documentation, the orchestrator routes directly to the LLM with no tool call and no retrieval step. The system prompt constrains the model to Payjack-relevant, read-only responses. This is the `safe_general_route` (`grounding_mode = "base"`).

Examples of messages that land here:
- "What is PayJack?"
- "How does mobile money work in Ghana?"
- "Can you explain what a recurring payment is?"

---

### Step 4: LLM Generation

The system sends:

- User message
- Tool outputs (if any — Tools and Hybrid routes only)
- Retrieved RAG context (if any — RAG and Hybrid routes only)
- System guardrails (all LLM routes)

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
| Compute | AWS Lambda container image for FastAPI via Mangum | Current |
| API front door | API Gateway HTTP API | Current |
| Container registry | Amazon ECR | Current |
| Secrets / configuration | IAM + env vars + Terraform wiring | Current |
| Logging / metrics hooks | CloudWatch-oriented runtime + telemetry modules | Current |
| Documentation buckets | Shared S3 KB source and artifacts buckets | Current |
| CDN for frontend | CloudFront with private S3 origin access control | Current |
| Legacy container service | ECS/Fargate modules retained in repo | Optional historical path |
| Managed Bedrock Knowledge Base resources | Possible later addition | Optional future seam |
| Datadog | Additional observability option | Optional future seam |

### Deployment Model

- Code -> GitHub
- CI/CD -> GitHub Actions
- Container -> Docker -> ECR
- Infrastructure -> Terraform
- Runtime Deploy -> Lambda + API Gateway
- Frontend Deploy -> S3 + CloudFront
- Storage -> S3 processed and KB artifacts

The active repo path is **GitHub Actions + Terraform + Docker + Lambda/API Gateway/CloudFront**, not TeamCity or Ansible AWX.

---

## 5. Current Repository Status and Integrations

| Capability | Current status | Implemented location | Notes |
|------------|----------------|----------------------|-------|
| Deterministic financial tools | Implemented | `app/tools/` | Tool-first vertical slice is in place |
| Structured data pipeline | Implemented | `app/data_pipeline/`, `scripts/dataset_transform.py` | Produces processed artifacts, QC, and manifest sidecars |
| Processed artifact repository layer | Implemented | `app/repository/` | Loads local or S3-backed processed datasets |
| Orchestration | Implemented | `app/orchestrator/` | Routes between tool, RAG, clarify, and refusal paths |
| Bedrock client abstraction | Implemented | `app/llm/` | Supports mock mode for local testing |
| RAG retrieval | Partially implemented | `app/rag/`, `kb/`, `scripts/kb_*.py` | Local/file path is ready; managed Bedrock KB remains optional |
| Backend API | Implemented | `app/api/`, `app/main.py` | FastAPI `/health`, `/ready`, and `/chat` |
| Next.js frontend | Implemented | `frontend/app/`, `frontend/components/`, `frontend/lib/` | Chat UI plus debug route |
| Frontend tests | Implemented | `frontend/*.config.ts`, `frontend/e2e/`, `frontend/tests/` | Vitest + Playwright |
| Backend tests | Implemented | `tests/` | Unit, integration, rag, llm, red-team, tool tests |
| Docker backend runtime | Implemented | `Dockerfile`, `Dockerfile.lambda` | Uvicorn for local/ECS compatibility; Lambda image for public deploys |
| Terraform bootstrap/env split | Implemented | `terraform/bootstrap/`, `terraform/` | Shared bootstrap plus environment stack |
| GitHub Actions workflows | Implemented | `.github/workflows/` | Bootstrap, plan, deploy, destroy |
| Shared KB buckets | Implemented | `terraform/bootstrap/main.tf` | Create-once shared KB source and KB artifacts buckets |
| CloudFront | Implemented | `terraform/modules/frontend_cloudfront/` | Public frontend and `/api/*` routing |
| Lambda | Implemented | `app/lambda_handler.py`, `terraform/modules/lambda_api/` | FastAPI adapter plus API Gateway HTTP API |

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

#### `/app`
Runtime application code deployed to Lambda for public environments, with the ASGI app still runnable locally through Uvicorn.

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

#### `/data`
Structured financial datasets and runtime artifacts.

- `raw/` -> source exports
- `processed/` -> canonical artifacts used by the repository layer
- `mock/` -> fixture-style data
- `embeddings/` -> optional local vector persistence

#### `/kb`
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
- root stack -> environment-specific Lambda, API Gateway, CloudFront, and S3 configuration

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
|-- app/
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
- Generate grounded responses (Tools, RAG, or Hybrid routes)
- Generate ungrounded responses from the LLM directly (LLM Direct / `safe_general_route`)

Agent logic includes:

- Route selection: `deterministic_tool_route`, `rag_route`, `hybrid_route`, `safe_general_route`, `clarification_route`, `refusal_route`
- Tool allowlists
- Clarification handling (static, no LLM call)
- Refusal handling (static, no LLM call)
- Audit logging on every route

The LLM Direct route (`safe_general_route`) is used for safe conversational and general questions. No tools are called and no documents are retrieved — the model responds within the constraints of the system prompt alone. This keeps latency low for simple questions while still applying the same safety and audit layers.

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
- real Bedrock enabled for answer-quality checks

### Runtime Entrypoints and Config Sources

- Local backend entrypoint: `app/main.py`
- Backend container entrypoint: `Dockerfile`
- Frontend local entrypoint: `frontend/app/page.tsx`
- Frontend debug route: `frontend/app/debug/page.tsx`
- Local backend configuration template: `.env.example`
- Local backend secrets/config source: auto-loaded `.env`
- Shared infrastructure bootstrap source of truth: `terraform/bootstrap/main.tf`
- Environment infrastructure source of truth: `terraform/main.tf`
- Deployment automation source of truth: `.github/workflows/`

### PowerShell

```powershell
cd C:\Users\Nii Quaynor\projects\Payjack-AI-Companion

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.dev.txt

python scripts\dataset_transform.py --source-mode local --local-root data\raw --output-dir data\processed --environment local
python scripts\kb_build.py
python scripts\embeddings_generate.py

$env:USE_MOCK_BEDROCK = "false"
$env:BEDROCK_MODEL_ID = "anthropic.claude-3-5-haiku-20241022-v1:0"

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open a second PowerShell window for the frontend:

```powershell
cd C:\Users\Nii Quaynor\projects\Payjack-AI-Companion\frontend

npm install
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
python -m pip install -r requirements.dev.txt

python scripts\dataset_transform.py --source-mode local --local-root data\raw --output-dir data\processed --environment local
python scripts\kb_build.py
python scripts\embeddings_generate.py

set USE_MOCK_BEDROCK=false
set BEDROCK_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In a second CMD window:

```cmd
cd C:\Users\Nii Quaynor\projects\Payjack-AI-Companion\frontend

npm install
set NEXT_PUBLIC_DEFAULT_USER_ID=dev-user
set NEXT_PUBLIC_DEFAULT_TENANT_ID=dev-tenant
set NEXT_PUBLIC_DEFAULT_ACCOUNT_IDS=acc-001

npm run dev
```

Local backend configuration is sourced from `.env.example` and the auto-loaded local `.env`.
During `npm run dev`, the frontend defaults to `http://127.0.0.1:8000` for API calls. Set `NEXT_PUBLIC_API_BASE_URL` only when you need to point at a different backend.
For local acceptance, set `USE_MOCK_BEDROCK=false`, set an explicit `BEDROCK_MODEL_ID`, and verify the responding model through `response.debug.model_id` in the frontend debug page or chat API response.

---

## 12. Testing

### Backend Tests

```powershell
cd C:\Users\Nii Quaynor\projects\Payjack-AI-Companion
.\.venv\Scripts\Activate.ps1

python -m pytest tests -q
python -m pytest tests --cov --cov-report=xml:coverage.xml --cov-report=term-missing -q
python scripts\run_coverage.py
```

If TeamCity is used for SonarQube analysis, run `python scripts/run_coverage.py`
in the checkout root immediately before the SonarQube Runner step. The script
fails if `coverage.xml` is not generated, which prevents Sonar from silently
analyzing the build with zero imported Python coverage.

For the Linux TeamCity agents used by the backend build, the coverage step can
use the checked-in helper:

```bash
bash scripts/teamcity_coverage.sh
```

The SonarQube Runner step must run after that command in the same checkout
directory and keep `sonar.python.coverage.reportPaths=coverage.xml`. If the
scanner log says `No report was found ... coverage.xml`, Sonar did not receive a
coverage file; rerun or fix the TeamCity command-line coverage step before
debugging Sonar settings.

The coverage report is configured through `.coveragerc` to emit repo-relative
Cobertura paths. If Sonar reports invalid `<source>` paths such as a developer
machine path (`C:\Users\...`), regenerate `coverage.xml` on the TeamCity agent
instead of reusing a local Windows-generated file.

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

The backend ships with a container definition in `Dockerfile`.

### Build

```powershell
cd C:\Users\Nii Quaynor\projects\Payjack-AI-Companion
docker build -f Dockerfile -t payjack-backend .
```

### Run

```powershell
cd C:\Users\Nii Quaynor\projects\Payjack-AI-Companion
docker run --rm -p 8000:8000 --env-file .env payjack-backend
```

For local-only mode, processed artifacts should already exist under `data/processed` before building and running the image. If the runtime is configured for S3-backed processed artifacts instead, local artifact generation is not required.

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

- Lambda function using the backend ECR image
- API Gateway HTTP API
- CloudFront distribution
- Private S3 frontend bucket
- IAM wiring
- Managed processed-artifacts bucket

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

## 15. Known Future Extensions

The following are valid integration directions, but they are not the active v1 public deployment path:

- **ECS/Fargate**: retained as historical/optional Terraform modules, but no longer the active public environment path
- **Custom domain**: Route53 and ACM are intentionally deferred; v1 uses the generated CloudFront URL
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
- Capable of answering safe general questions via LLM directly, without any tool calls or retrieval (`safe_general_route`)
- Orchestrated through a controlled workflow engine with four active routes: Tools, RAG, Hybrid, and LLM Direct
- Deployable on Lambda/API Gateway/CloudFront through GitHub Actions, Terraform, and Docker
- Designed for compliance and auditability from day one

It transforms raw transaction history into understandable financial insight without ever touching execution systems.
