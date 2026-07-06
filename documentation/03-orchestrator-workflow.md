# Orchestrator Workflow

> **Question this diagram answers:** What does the orchestrator do internally between receiving a request and returning a response?

The orchestrator is the coordination engine of the Payjack AI Companion. It is responsible for validating input, enforcing policy, selecting a route, assembling context, calling Bedrock, formatting output, and recording every step for auditing.

```mermaid
flowchart TD
    subgraph INPUT ["Input"]
        A["Incoming request\nUser message · account context · session state"]
    end

    subgraph GUARD ["Policy + Validation"]
        B["Parameter validation\nRequired fields · type checks · length limits"]
        C["Policy guard\nRead-only contract · no-execution · no-advice"]
        B --> C
    end

    subgraph MEMORY ["Session Memory"]
        SM["Session memory lookup\nPer-session_id turn history + last tool facts"]
        SF{"Contextual follow-up\nresolvable?"}
        SM --> SF
    end

    subgraph CLASSIFY ["Intent Classification"]
        D["Intent classifier\nRoute selection from message + context"]
        E{"Route decision"}
        D --> E
    end

    subgraph CONTEXT ["Context Assembly"]
        F["Tool invocation\nDeterministic financial queries"]
        G["RAG retrieval\nTop-k KB chunks · metadata filters"]
        H["Context builder\nMerges tool output + KB chunks + system prompt"]
        F --> H
        G --> H
    end

    subgraph MODEL ["Model Layer"]
        I["LLM prompt assembly\nSystem prompt · context · user message"]
        J["🤖 Amazon Bedrock\nFoundation model generation"]
        I --> J
    end

    subgraph OUTPUT ["Output + Observability"]
        K["Response formatter\nStructure · tables · step-by-step guidance"]
        L["Audit logging\nRoute taken · tool calls · model call metadata"]
        M["Telemetry\nLatency · tokens · retrieval quality · errors"]
        K --> L --> M
    end

    A --> B
    C --> SM

    SF -->|Yes| SR(["💬 Cached follow-up answer — exits here"])
    SF -->|No| D

    E -->|Tool route| F
    E -->|RAG route| G
    E -->|Hybrid route| F & G
    E -->|LLM Direct| H
    E -->|Clarification| N(["❓ Static clarification — exits here"])
    E -->|Refusal| O(["🚫 Static refusal — exits here"])

    H --> I
    J --> K
    M --> P(["Structured response returned to caller"])
```

---

## Responsibility Boundary

The orchestrator owns two clearly separated concerns:

| Concern | Owned by |
|---|---|
| Route selection, tool calls, RAG retrieval, context assembly, output formatting | **Orchestrator** (deterministic runtime) |
| Natural language generation from assembled context | **Bedrock** (model layer) |

The model never receives raw financial data. It receives only structured, pre-processed context assembled by the orchestrator.

Session memory (`backend/app/memory/session_memory.py`) is intentionally narrow: it holds the last few turns and structured tool facts per `session_id`, in-process only, and is lost on Lambda cold start or restart. It is not durable chat history and never stores free-form assistant text as a source of truth for follow-ups — only structured facts from the last tool-backed response.

Request identity (`user_id`, `tenant_id`, `roles`, `account_ids`) is derived by `AuthContext.from_headers` (`backend/app/security/auth_context.py`) directly from client-supplied headers (`x-payjack-user-id`, `x-payjack-tenant-id`, `x-payjack-roles`, `x-payjack-account-ids`), with no independent verification — the orchestrator trusts whatever the calling application (the Payjack App) asserts. `access_control.py::resolve_account_scope` then restricts any requested `account_ids` to the set already present in that header.

---

## Route Termination Points

Clarification and refusal routes exit **before** any LLM call. They return a static response directly from the orchestrator, which means:

- Zero Bedrock cost for these paths
- Zero hallucination risk for these paths
- Deterministic, auditable outputs for every refused or clarified request

A resolved session-memory follow-up exits even earlier — before intent classification runs at all — and is answered from the last tool-backed response's structured facts rather than from any new tool call or model generation.

---

*Previous: [02 — Runtime Workflow](02-runtime-workflow.md) · Next: [04 — Tool Routing](04-tool-routing.md)*
