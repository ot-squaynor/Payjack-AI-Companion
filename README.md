# Payjack-AI-Companion
Internal/External Finance Fine Tuned Multi-Agent Chatbot

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
- RAG-grounded (no hallucinated policy answers)
- Agent-enabled (can route between tools and documentation)
- Fully deployable inside OrangeTech’s AWS infrastructure

---

## 2. High-Level Architecture

The system has three primary intelligence layers:

1. **Tools Layer (Structured Data Access)**
2. **RAG Layer (Knowledge Retrieval)**
3. **LLM Generation Layer (Natural Language Responses)**

These are coordinated by an **AI Orchestrator**.

### Conceptual Flow

User → Chat Interface → Orchestrator →  
→ (Tool Calls OR RAG Retrieval OR Both) →  
→ LLM Response Generation →  
→ Structured Output → User

---

## 3. How It Works (End-to-End)

### Step 1: User Asks a Question

Example:
- “How much did I spend on food last month?”
- “Why is my transfer still pending?”
- “How do I split a bill?”

---

### Step 2: Intent Classification

The Orchestrator determines:

- Transaction question → use Tools
- Feature explanation → use RAG
- Mixed → use both
- Disallowed (advice/execution) → refuse safely

---

### Step 3A: Tools (Structured Financial Data)

The system calls read-only internal functions:

- Transaction lookup
- Spend summary
- Recurring detection
- Status explanation
- Product balances (if available)

These return **structured JSON**.

---

### Step 3B: RAG (Knowledge Retrieval)

If explanation is required:

1. Query Knowledge Base
2. Retrieve top relevant document chunks
3. Filter by metadata
4. Pass retrieved context to LLM

This ensures:
- Policy answers are grounded
- No hallucinated fees or limits

---

### Step 4: LLM Generation

The system sends:

- User message
- Tool outputs (if any)
- Retrieved RAG context (if any)
- System guardrails

to a **Bedrock foundation model**.

The model generates:
- Structured conversational response
- Tables where needed
- Step-by-step guidance

---

### Step 5: Safety Layer

Before returning output:

- PII masking applied
- Policy guard checks (no execution, no advice)
- Audit logging
- Telemetry recording

---

## 4. How It Works With AWS

The system is deployed entirely inside AWS.

### Core Services

| Layer | AWS Service |
|-------|------------|
| LLM | Amazon Bedrock |
| RAG Docs | S3 + Bedrock Knowledge Base |
| Compute | ECS (containers) |
| Data | RDS (read-only structured data) |
| Secrets | AWS Secrets Manager |
| Encryption | AWS KMS |
| Identity | IAM |
| Logging | CloudWatch |
| Monitoring | DataDog |

---

### Deployment Model

- Code → GitHub
- CI → TeamCity
- Container → Docker
- Deploy → Ansible AWX → ECS
- Monitor → DataDog

The system runs as a containerized FastAPI service on ECS.

---

## 5. Why the File Structure Is Designed This Way

The repository is structured by **system responsibility**, not by technology.

### Core Principles

1. **Separation of concerns**
2. **LLM abstraction layer**
3. **Data isolation**
4. **Security isolation**
5. **Scalability readiness**

---

### Folder Logic

#### `/backend/app`
Runtime application code deployed to ECS.

Separated into:
- `api/` → HTTP layer
- `orchestrator/` → reasoning logic
- `llm/` → model abstraction
- `rag/` → retrieval logic
- `tools/` → financial logic
- `security/` → compliance logic
- `telemetry/` → logging & cost tracking

---

#### `/backend/data`
Data layer (not all committed to Git).

- `raw/` → corp exports
- `processed/` → cleaned data
- `embeddings/` → vectorized documents
- `mock/` → test data

Separating raw and processed data prevents corruption and improves reproducibility.

---

#### `/backend/kb`
Knowledge base content.

- Raw help center exports
- Cleaned Markdown
- Metadata
- Chunking rules

This feeds RAG.

---

#### `/experiments`
Fine-tuning and prompt experiments.

Allows:
- Controlled experimentation
- Model evaluation
- Regression testing

---

#### `/terraform`

Infrastructure as Code (AWS).

- ECS service definitions
- IAM roles
- Bedrock configuration
- KMS encryption policies
- S3 storage definitions

Supports reproducible, auditable deployments.

---

#### `/frontend`

User interface layer.

- Chat interface for interacting with the AI companion
- Displays tool outputs and RAG responses
- Can be extended with session history and visual analytics

---

#### `/memory`

Optional storage for session state.

- Used for local development or conversational continuity
- Not used for sensitive production persistence

---

## 6. Data Pipelines

There are two main pipelines.

---

### A. Financial Data Pipeline

Raw transaction data →  
Normalization →  
Recurring detection →  
Structured tool access

This is **non-predictive** and descriptive only.

---

### B. RAG Pipeline

Documentation →  
Markdown conversion →  
Metadata tagging →  
Chunking →  
Embedding →  
Vector storage (Bedrock KB)  

This pipeline ensures retrieval accuracy.

---

## 7. Agents & Orchestration

The system behaves like a lightweight agent.

It can:

- Classify intent
- Call tools
- Retrieve documents
- Merge structured + unstructured context
- Generate grounded responses

Agent logic includes:

- Tool allowlist
- Clarification loop
- Failure handling
- Audit logging

This makes the AI controlled, not autonomous.

---

## 8. Security & Compliance Model

The system is built with:

- Read-only architecture
- Least-privilege IAM
- Encryption at rest (KMS)
- Encryption in transit (TLS)
- PII masking before LLM calls
- Audit logs for tool usage
- Guardrails against execution/advice

This aligns with:

- PCI-DSS (secure data handling)
- ISO 27001 (access control & monitoring)

---

## 9. Observability & Cost Control

The system tracks:

- Model latency
- Tool call counts
- Retrieval hit rate
- Token usage
- Error rates
- Cost per session

Alerts trigger on:

- Latency spikes
- Failure spikes
- Cost anomalies

---

## 10. Summary

The Payjack AI Financial Companion is:

- A secure, read-only AI interpretation layer
- Powered by Bedrock
- Grounded using RAG
- Structured using financial tools
- Orchestrated through agent logic
- Deployed on ECS
- Monitored via DataDog
- Designed for compliance from day one

It transforms raw transaction history into understandable financial insight — without ever touching execution systems.

---

## Final State

When complete, the system provides:

- Grounded explanations
- Structured spend summaries
- Safe in-app guidance
- Pattern recognition
- Clear boundaries
- Full auditability
- Production-grade infrastructure alignment

---
## 📦 Repository Overview

The Payjack AI Financial Companion repository is structured to support a secure, modular, production-grade AI system deployed on AWS ECS and powered by Amazon Bedrock.

The architecture separates responsibilities clearly across application logic, data processing, retrieval systems, financial tools, security enforcement, testing, and infrastructure.

This ensures:

- Clean separation of concerns  
- Read-only financial data handling  
- RAG-grounded documentation responses  
- Strict compliance enforcement  
- Scalable microservice evolution  
- Enterprise deployment readiness  

---

## 📁 Folder Structure
```
payjack-ai-companion/
│
├── backend/                     # Core backend runtime, config, datasets, KB, and tests
│   ├── app/                     # Application runtime deployed via Docker/ECS
│   │   ├── api/                 # HTTP routes and schemas
│   │   ├── data_pipeline/       # Data cleaning, normalization, QC, and recurrence prep
│   │   ├── llm/
│   │   │   ├── autoregressive/  # Bedrock generative model clients and streaming logic
│   │   │   └── embedding/       # Vector/encoding model clients and embedding utilities
│   │   ├── orchestrator/        # Intent routing and workflow coordination
│   │   ├── rag/                 # Retrieval-Augmented Generation logic
│   │   ├── security/            # PII redaction, access control, and guardrails
│   │   ├── telemetry/           # Logging, metrics, and cost tracking
│   │   └── tools/               # Read-only deterministic financial tools
│   │
│   ├── data/                    # Backend-local structured datasets for tooling and dev
│   │   ├── embeddings/          # Vectorized datasets / local vector persistence
│   │   ├── mock/                # Synthetic test data
│   │   ├── processed/           # Cleaned and standardized datasets
│   │   └── raw/                 # Raw corp exports or source datasets
│   │
│   ├── kb/                      # Backend Knowledge Base for RAG
│   │   ├── metadata/            # Retrieval metadata definitions and manifests
│   │   ├── processed_docs/      # Cleaned and chunked Markdown docs
│   │   └── raw_docs/            # Original documentation exports
│   │
│   ├── tests/                   # Backend system validation
│   │   ├── evaluation/          # Eval scripts and test sets
│   │   ├── fixtures/            # Mock inputs and sample payloads
│   │   ├── integration/         # Route and end-to-end backend integration tests
│   │   ├── llm_tests/           # Bedrock/LLM behavior and contract tests
│   │   ├── rag_tests/           # Retrieval and metadata enforcement tests
│   │   ├── red_team_tests/      # Prompt injection and policy abuse tests
│   │   ├── tool_tests/          # Deterministic tool integrity tests
│   │   └── unit/                # Low-level unit tests
│   │
│   ├── Dockerfile               # Backend container definition
│   ├── requirements.txt         # Backend Python dependencies
│   └── .env.example             # Backend environment variable template
│
├── frontend/                    # UI layer for chat and user interaction
│   ├── app/                     # Frontend app routes and pages
│   └── public/                  # Static frontend assets
│
├── memory/                      # Optional local/session memory storage
│
├── scripts/                     # Operational and deployment utilities
│
├── terraform/                   # Infrastructure as Code for AWS resources
│   ├── modules/
│   │   ├── bedrock/             # Bedrock-related infra modules
│   │   ├── ecs/                 # ECS service/task infra modules
│   │   ├── iam/                 # IAM roles and policy modules
│   │   ├── kms/                 # KMS encryption modules
│   │   └── s3/                  # S3 bucket and storage modules
│   ├── main.tf                  # Root Terraform resources
│   ├── outputs.tf               # Terraform outputs
│   ├── terraform.tfvars         # Default Terraform variable values
│   ├── variables.tf             # Terraform input variables
│   └── versions.tf              # Terraform/provider version constraints
│
├── prototype/                   # Experimental and non-production work
│
└── README.md                    # Project overview and architecture guide
```
---

## 🧠 Structural Logic

- `app/` contains all runtime logic deployed to AWS ECS.
- `tools/` modules are deterministic and return structured financial data.
- `rag/` ensures documentation-grounded responses.
- `llm/` isolates all Bedrock interaction.
- `security/` centralizes compliance and policy enforcement.
- `data_pipeline/` ensures raw financial data is normalized before interpretation.
- `infra/` documents deployment and cloud configuration.
- `tests/` protects system integrity before release.

This structure is intentionally modular to support future scaling, microservice separation, and strict regulatory review.

The system is designed to be:

- Read-only  
- Transaction-led  
- RAG-grounded  
- Agent-orchestrated  
- PCI-aligned  
- ISO27001-aligned  
- AWS-native  
**This repository represents the complete foundation for a scalable, secure AI financial companion within OrangeTech’s AWS ecosystem.**
