# Data Pipeline

> **Question this diagram answers:** How does raw financial data become the structured artifacts that tool queries run against?

The data pipeline is an **offline process** — it does not run per request. It transforms raw financial exports into standardized, quality-checked Parquet artifacts that the runtime repository layer loads at startup.

---

## Pipeline Flow

```mermaid
flowchart TD
    subgraph SOURCES ["📥 Raw Data Sources — external, never destroyed by Terraform"]
        S1["EXTERNAL_TRANSACTIONS_BUCKET\nTransaction exports"]
        S2["EXTERNAL_ACCOUNTS_BUCKET\nAccount data"]
        S3["EXTERNAL_FEES_BUCKET\nFee and limit data"]
        S4["EXTERNAL_PRODUCTS_BUCKET\nProduct metadata"]
        S5["EXTERNAL_METADATA_BUCKET\nAdditional metadata"]
    end

    subgraph PIPELINE ["⚙️ Offline Pipeline — scripts/dataset_transform.py (CLI) orchestrating backend/app/data_pipeline/"]
        P1["Ingestion\ningestion.py\nLoad raw exports from local disk or S3"]
        P2["Normalization\nnormalization.py + processed_schema.py\nStandardize schema · type coercion · date parsing"]
        P3["Category mapping\ncategory_mapping.py\nMap merchant codes to spend categories"]
        P4["Recurring detection\nrecurring_logic.py\nIdentify subscription and recurring patterns"]
        P5["Quality checks\nquality_checks.py\nRow counts · null rates · schema validation"]
        P1 --> P2 --> P3 --> P4 --> P5
    end

    subgraph ARTIFACTS ["📦 Processed Artifacts"]
        A1["transactions.parquet\nCanonical processed transaction records"]
        A2["accounts.parquet\nNormalized account and balance data"]
        A3["manifest.json\nDataset version · artifact paths · build metadata"]
        A4["qc_report.json\nMachine-readable quality check results"]
        A5["pipeline_summary.json\nHuman-readable pipeline run summary"]
    end

    subgraph RUNTIME ["⚡ Runtime — per request"]
        REPO["Repository layer\nprocessed_store.py\nLoads artifacts at startup from local disk or S3"]
        TOOLS["Deterministic tools\ntransaction_lookup · spend_summary · balances\nrecurring_detection · status_explanation · fee_breakdown"]
        LLM["🤖 Bedrock\nTool output injected as grounding context"]
        REPO --> TOOLS --> LLM
    end

    S1 & S2 & S3 & S4 & S5 --> P1
    P5 --> A1 & A2 & A3 & A4 & A5
    A1 & A2 --> |Published to managed S3 artifacts bucket at deploy| REPO
    A3 --> REPO
```

> `scripts/dataset_transform.py` is a thin CLI entrypoint — the actual ingestion, normalization, category-mapping, recurring-detection, and quality-check logic lives in `backend/app/data_pipeline/` as importable modules, which the script calls in sequence.

---

## Artifact Reference

| Artifact | Format | Purpose | Consumed by |
|---|---|---|---|
| `transactions.parquet` | Parquet | Canonical processed transactions | Repository layer, tool queries |
| `accounts.parquet` | Parquet | Normalized account and balance records | Repository layer, tool queries |
| `manifest.json` | JSON | Dataset version, artifact paths, source metadata, build info | Repository layer, runtime health, audits |
| `qc_report.json` | JSON | Machine-readable quality check results | Pipeline validation, QA |
| `pipeline_summary.json` | JSON | Human-readable pipeline run summary | Developer inspection, ops review |

---

## Source Mode Switching

The pipeline supports two source modes, controlled by the `--source-mode` flag:

| Mode | When used | Data location |
|---|---|---|
| `local` | Local development | `backend/data/raw/` on disk |
| `s3` | CI/CD deployment | External S3 buckets via `EXTERNAL_*_BUCKET` env vars |

> External raw-data buckets are **never** destroyed by Terraform. The destroy workflow checks that managed bucket outputs do not match any external bucket name before emptying managed buckets.

---

*Previous: [05 — RAG Workflow](05-rag-workflow.md) · Next: [07 — Deployment Workflow](07-deployment-workflow.md)*
