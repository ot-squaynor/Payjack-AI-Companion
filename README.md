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

#### `/app`
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

#### `/data`
Data layer (not all committed to Git).

- `raw/` → corp exports
- `processed/` → cleaned data
- `embeddings/` → vectorized documents
- `mock/` → test data

Separating raw and processed data prevents corruption and improves reproducibility.

---

#### `/kb`
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

#### `/infra`
Infrastructure definitions.

- ECS configs
- IAM roles
- Bedrock configs
- KMS policies
- S3 policies

Keeps infra version-controlled and auditable.

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

**This repository represents the complete foundation for a scalable, secure AI financial companion within OrangeTech’s AWS ecosystem.**
