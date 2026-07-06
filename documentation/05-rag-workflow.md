# RAG Workflow

> **Question this diagram answers:** How are documentation chunks prepared offline and retrieved at runtime to ground LLM responses?

RAG (Retrieval Augmented Generation) ensures that answers to documentation questions — fees, limits, feature explanations, error codes — are grounded in Payjack's actual policy and help content, not in the model's parametric knowledge.

The pipeline has two distinct phases: an **offline build phase** that runs before deployment, and a **runtime retrieval phase** that runs per request.

---

## Offline Pipeline — Build Phase

```mermaid
flowchart TD
    subgraph OFFLINE ["📦 Offline KB Pipeline — runs before deployment"]
        direction TD
        D1["📁 Raw documents\nbackend/kb/raw_docs/\nhelp_center · fees · limits · features · errors"]
        D2["🧹 Cleaning\nNormalise whitespace · strip irrelevant content"]
        D3["✂️ Chunking\nSplit into retrieval-sized passages"]
        D4["🏷️ Metadata attachment\nCategory · source file · topic tags"]
        D5["🔢 Embedding generation\nscripts/embeddings_generate.py\nBedrock embedding model"]
        D6["💾 Vector store\nbackend/kb/processed_docs/\nchunks.jsonl · embeddings.jsonl"]
        D7["📋 KB manifest\nbackend/kb/metadata/kb_manifest.json\nBuild metadata · source file index"]

        D1 --> D2 --> D3 --> D4 --> D5 --> D6
        D5 --> D7
    end

    D6 -->|"Published to shared S3 KB artifacts bucket\nscripts/kb_publish.py"| S3["☁️ Shared S3 KB artifacts bucket\nPersists across environment teardown"]
```

> KB ingestion (`backend/app/rag/kb_builder.py`) is not limited to prose documents. Structured source files are also supported: **CSV** files are chunked one summary chunk plus one chunk per data row, and **Excel workbooks** (`.xls`/`.xlsx`/`.xlsm`, via `pandas`) are chunked one summary chunk per sheet. Both paths flow through the same cleaning, metadata-attachment, and embedding stages as text documents.

---

## Runtime Retrieval Phase

```mermaid
flowchart TD
    subgraph RUNTIME ["⚡ Runtime Retrieval — per request"]
        direction TD
        R1["💬 User question"] --> R2["🔢 Query embedding\nSame embedding model as offline build"]
        R2 --> R3["🔍 Retriever\nbackend/app/rag/\nVector similarity search"]
        R3 --> R4["🏷️ Metadata filters\nCategory · topic · source"]
        R4 --> R5["📝 Top-k chunks\nHighest-relevance passages selected"]
        R5 --> R6["📐 Prompt builder\nChunks injected as context"]
        R6 --> R7["🤖 Bedrock\nGrounded generation with retrieved context"]
        R7 --> R8(["💬 Grounded answer returned to user"])
    end

    S3["☁️ Shared S3 KB artifacts bucket"] -->|Loaded at Lambda cold start or on demand| R3
```

---

## KB Source Categories

| Folder | Content |
|---|---|
| `raw_docs/help_center/` | User support articles, FAQs — wallet, card, transfers, account |
| `raw_docs/fees/` | Fee explanations — transfers, card, withdrawal |
| `raw_docs/limits/` | Transaction and account limits — transfers, ATM, card, wallet |
| `raw_docs/features/` | Product feature documentation — wallet, transfers, card |
| `raw_docs/errors/` | Error code explanations — transfers, authentication, general |

---

## Key Guarantees

- **No financial data in RAG** — KB documents contain no customer-specific or PII information
- **Citeable** — every retrieved chunk has a source and category in its metadata
- **Grounded** — model cannot fabricate policy; it is constrained to retrieved context
- **Shared and persistent** — KB artifacts bucket survives environment teardown

---

*Previous: [04 — Tool Routing](04-tool-routing.md) · Next: [06 — Data Pipeline](06-data-pipeline.md)*
