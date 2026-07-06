# Tool Routing

> **Question this diagram answers:** How are deterministic financial tools selected and executed, and how do their outputs reach the user?

The tools layer provides structured, deterministic access to processed financial data. Tools are read-only functions that query processed Parquet artifacts loaded by the repository layer. Their outputs are JSON — never raw database records — and are injected into the LLM prompt as grounding context.

```mermaid
flowchart TD
    A("💬 User question") --> B["🧠 Orchestrator\nIntent classified as tool or hybrid route"]
    B --> C["🗂️ Tool registry\nSelects one or more tools based on intent"]

    subgraph TOOLS ["🛠️ Deterministic Tools — executed in parallel where applicable"]
        T1["transaction_lookup\nFind specific transactions by date, merchant, amount"]
        T2["spend_summary\nAggregate spend by category or period"]
        T3["balances\nCurrent and available product balances"]
        T4["recurring_detection\nIdentify recurring charges and subscriptions"]
        T5["status_explanation\nInterpret transaction or transfer status codes"]
        T6["fee_breakdown\nExplain fees applied to an account or transaction"]
    end

    C --> T1 & T2 & T3 & T4 & T5 & T6

    T1 & T2 & T3 & T4 & T5 & T6 --> D["📊 Structured JSON output\nNormalized, PII-checked results"]
    D --> E["🤖 Bedrock\nTool output injected into prompt as grounding context"]
    E --> F["📋 Response formatter\nNatural language explanation of tool results"]
    F --> G(["💬 Response returned to user"])
```

> Tools are also reachable directly via `POST /tools/invoke` (`backend/app/api/routes_tools.py`), which returns the raw structured JSON result to the frontend's tool-invoke UI without going through the orchestrator or Bedrock. See [01 — System Overview](01-system-overview.md).

---

## Data Path for Tool Queries

```mermaid
flowchart LR
    subgraph OFFLINE ["Offline — Data Pipeline"]
        R["Raw exports\nCSV / JSON from banking systems"]
        P["dataset_transform.py\nNormalization · category mapping · quality checks"]
        A["Processed artifacts\ntransactions.parquet · accounts.parquet · manifest.json"]
        R --> P --> A
    end

    subgraph RUNTIME ["Runtime — Tool Execution"]
        REPO["Repository layer\nprocessed_store.py\nLoads artifacts from local disk or S3"]
        TOOL["Tool functions\nbackend/app/tools/"]
        JSON["Structured JSON result"]
        REPO --> TOOL --> JSON
    end

    A -->|Published to S3 at deploy time| REPO
```

---

## Tool Descriptions

| Tool | Input | Output | Use case |
|---|---|---|---|
| `transaction_lookup` | Date range, merchant, amount filters | Matching transaction records | "Show me my Bolt transactions last week" |
| `spend_summary` | Category, time period | Aggregated totals | "How much did I spend on food in March?" |
| `balances` | Account identifiers | Current and available balances | "What is my wallet balance?" |
| `recurring_detection` | Transaction history | Detected recurring patterns | "What subscriptions am I paying for?" |
| `status_explanation` | Status code or transaction ID | Human-readable explanation | "Why is my transfer still pending?" |
| `fee_breakdown` | Account or product identifiers | Applied fees and charges | "What fees apply to my withdrawal?" |

---

## Key Guarantees

- **Deterministic** — same inputs always produce the same outputs
- **Read-only** — tools never write to any system
- **Auditable** — every tool invocation is recorded in the audit log
- **Isolated** — a customer's actual financial data (balances, transactions, fees charged) is never retrieved via RAG; only tools can return it. RAG's `fees/` knowledge-base category is a separate, distinct source — general fee *policy* documentation (e.g. "what fees exist and why"), never a customer's specific fee history. See [05 — RAG Workflow](05-rag-workflow.md).

---

*Previous: [03 — Orchestrator Workflow](03-orchestrator-workflow.md) · Next: [05 — RAG Workflow](05-rag-workflow.md)*
