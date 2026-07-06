# Documentation Gap Analysis Report

> Point-in-time audit of `documentation/01-system-overview.md` through `10-end-to-end-user-journey.md` against the `react-version` branch as of 2026-07-06. This file is an audit artifact, not part of the living 01→10 sequence, and is not included in their prev/next navigation chain.

## Documents Reviewed

| Doc | Purpose |
|---|---|
| 01 — System Overview | Top-level component diagram and design principles |
| 02 — Runtime Workflow | Full request/response lifecycle and six-route intent classification |
| 03 — Orchestrator Workflow | Internal orchestrator stages: validation, policy, routing, context, model call, output |
| 04 — Tool Routing | Deterministic financial tools and their data path |
| 05 — RAG Workflow | Offline KB build and runtime retrieval pipelines |
| 06 — Data Pipeline | Offline transformation of raw exports into Parquet artifacts |
| 07 — Deployment Workflow | CI/CD pipeline from push to running AWS environment |
| 08 — AWS Services | Inventory of AWS services grouped by responsibility |
| 09 — Folder Architecture | Full repository folder/file structure and responsibilities |
| 10 — End-to-End User Journey | Worked example tracing one question through every layer |

Every claim in these documents was cross-checked directly against `backend/`, `frontend/`, `terraform/`, and `.github/workflows/` source — not inferred from the docs' own internal consistency.

## Major Inconsistencies Found (corrected)

- **Streaming chat claim was false.** Docs 01 and 02 described the frontend as a "streaming chat interface." `backend/app/llm/autoregressive/streaming_handler.py` is a docstring-only stub and `frontend/lib/api.ts` performs a single non-streaming `fetch`. Both docs now describe a request/response chat UI.
- **`fee_breakdown` tool was undocumented.** `backend/app/tools/registry.py` wires six tools, but docs 04 and 06 only listed five. Added to both, plus a boundary clarification against RAG's `fees/` KB category (tool = customer-specific figures, RAG = general policy text).
- **Session memory was entirely undocumented** despite being a real, load-bearing control-flow branch. `WorkflowEngine.handle_chat` checks `backend/app/memory/session_memory.py` before intent classification and can short-circuit straight to a cached answer for follow-ups like "so how many GHS." Added as a first-class step to docs 02 and 03.
- **`POST /tools/invoke` was undocumented.** This endpoint (`backend/app/api/routes_tools.py`) lets the frontend's tool-invoke UI call a tool directly, bypassing the orchestrator and Bedrock entirely — a second entry point into the system that docs 01, 02, 04, and 09 didn't acknowledge. Now referenced in all four.
- **Doc 10's flagship worked example used a fabricated tool-output schema.** The example asserted `status_explanation`/`transaction_lookup` return `{ status, code, initiated_at }`. In reality, `status_explanation` returns an aggregate `counts_by_status` distribution (no per-transaction lookup, no `code`/`initiated_at` fields), and `TransactionRecord` has no `status` field at all. Corrected the diagram, step table, and added an explicit "requires verification" callout — this is flagged for the team rather than silently resolved, since it may represent a real product gap (no dedicated per-transaction status lookup exists yet).

## Missing Documentation Discovered (added)

- CSV and Excel ingestion into the RAG knowledge base (`backend/app/rag/kb_builder.py::load_csv_chunks`/`load_excel_chunks`) — doc 05 previously only described prose-document chunking.
- The real internal structure of `backend/app/llm/` — `autoregressive/`, `embedding/`, `prompts/` subpackages, plus a top-level `fine_tuning.py` of unclear status — doc 09 previously had one flat line.
- The real file list under `backend/app/security/` (`parameter_validator.py`, `pii_redaction.py`, `policy_guard.py`, `audit_logging.py`, `auth_context.py`, `access_control.py`) and the header-based `AuthContext` auth model it implements — previously undocumented anywhere in the set.
- `backend/app/memory/` (session memory) — absent from doc 09's folder tree entirely.
- The evaluation tooling in `scripts/` (`eval_run_e2e.py`, `eval_run_rag.py`, `eval_run_route_batch.py`, `eval_run_tool_integrity.py`, `eval_summarize.py`, `chat_eval_common.py`) — none were listed in doc 09.
- Unwired Terraform modules `modules/ecs/`, `modules/bedrock/`, `modules/kms/`, `modules/network/`, plus `terraform/oidc-setup/` and `terraform/TERRAFORM_GUIDE.md` — none appeared in doc 09's tree.
- Frontend `hooks/use-chat-history.ts` and the current full `components/` list (`app-header`, `chat-shell`, `chat-history-sidebar`, `message-list`, `message-input`, `message-actions`, `response-card`, `tool-menu`, `tool-result-card`, `toast`) — doc 09 previously had one generic line for each.
- `plan-env.yml`'s automatic pull-request trigger (on changes under `backend/`, `frontend/`, `scripts/`, `terraform/`, `.github/workflows/`) — doc 07's workflow table said "Manual — before deploy" only.

## Outdated Sections Corrected

- Doc 09's `tests/evaluation` description said "future eval runners" — the folder (`eval.py`, `test_companion_quality.py`, `test_route_prompt_batches.py`, `route_batches/`) already exists and is populated. Changed to present tense.
- Doc 06's pipeline diagram implied the five processing stages lived inside `scripts/dataset_transform.py` itself. In reality the script is a thin CLI that imports `backend/app/data_pipeline/{ingestion,normalization,category_mapping,recurring_logic,quality_checks,processed_schema}.py`. Diagram nodes now name the actual modules.

## New Sections Added

- 01: dual entry-point note (`/chat` orchestrator path vs. `/tools/invoke` direct path).
- 02: session-memory branch node and Route Reference row; note on `/tools/invoke` as a parallel entry.
- 03: Session Memory subgraph with an early-exit branch; auth-model and session-memory-scope notes in the Responsibility Boundary section.
- 04: `fee_breakdown` tool node/table row; tool-vs-RAG fee boundary clarification.
- 05: CSV/Excel structured-source ingestion note.
- 06: named `app/data_pipeline/` submodules; `fee_breakdown` added to the runtime tool list.
- 08: three-way `BEDROCK_MODEL_ID` default mismatch, flagged for reconciliation rather than asserted as fact.
- 09: expanded `app/llm/`, `app/security/` file lists; new `app/memory/` entry; `/tools/invoke` route row; full eval-script list; unwired Terraform modules and missing `terraform/` subfolders; full frontend `components/`/`hooks/` listing.
- 10: corrected tool-output schema; session-memory cross-reference; "requires verification" callout on per-transaction status-explanation capability.

## Diagrams Updated

Mermaid diagrams changed in: **02** (session-memory branch), **03** (Session Memory subgraph + edges), **04** (sixth tool node + fan-out), **06** (renamed pipeline stage nodes), **09** (mindmap — llm/security/memory expansion, terraform modules), **10** (tool-output node label). Diagrams in 01, 05, 07, 08 were left structurally unchanged (only surrounding text/table edits).

## Cross-References Introduced

- 01 ↔ 04 ↔ 09: `/tools/invoke` direct-invoke path.
- 02 ↔ 03: session-memory contextual follow-up mechanism.
- 04 ↔ 05: tool vs. RAG boundary for fee-related data.
- 10 ↔ 03: session-memory follow-up caching applied to the worked example.

## Items Flagged "Requires Verification" (not resolved, per validation rule — do not fabricate)

1. **`BEDROCK_MODEL_ID` has three different defaults**: `backend/app/config.py` (`anthropic.claude-3-5-haiku-20241022-v1:0`), `backend/.env.example` (`eu.amazon.nova-micro-v1:0`), `.github/workflows/deploy-env.yml` and `plan-env.yml`/`destroy-env.yml` (`amazon.nova-micro-v1:0`). These should be reconciled to one source of truth.
2. **Terraform modules `ecs/`, `bedrock/`, `kms/`, `network/`, and `iam/`** exist under `terraform/modules/` but are not referenced by root `terraform/main.tf` (which only wires `s3`, `lambda_api`, `frontend`). Unclear if vestigial (e.g., from an earlier ECS-based design predating the Lambda path) or reserved for future use.
3. **`backend/app/llm/fine_tuning.py`** exists but its role could not be determined from a directory listing; needs a source read or team confirmation before documenting its behavior.
4. **`fee_breakdown`'s exact data source** was not fully traced (it imports `pandas` directly rather than the shared `processed_store.py` repository layer used by other tools) — worth confirming during a follow-up pass whether it reads `data/processed/` artifacts the same way the other five tools do.
5. **Per-transaction status explanation** (doc 10's original narrative) exceeds what `status_explanation` currently implements (aggregate counts only, no `transaction_id` filter, no `code`/`initiated_at` fields). Confirm whether this is a planned enhancement or whether the worked-example narrative should be scoped down permanently.

## Recommendations for Long-Term Documentation Maintenance

- Add a PR checklist item (or a lightweight CI check that diffs `backend/app/tools/`, `backend/app/api/`, `backend/app/memory/`, and `terraform/`) reminding contributors to update the corresponding `documentation/*.md` file when these paths change — this drift accumulated over roughly a dozen commits in under two weeks.
- Treat `documentation/09-folder-architecture.md` as the canonical structural source of truth and keep its reference tables (not just the mindmap) in sync — the mindmap alone tends to be updated while the detail tables lag behind, which is exactly how several of the gaps above accumulated.
- When a tool's output schema changes (as with `status_explanation`), grep `documentation/` for the tool name as part of the change — doc 10's stale example would have been caught immediately by this habit.
- Resolve the `BEDROCK_MODEL_ID` three-way mismatch before the next doc pass so 08 can state a real default instead of a "requires verification" callout.
