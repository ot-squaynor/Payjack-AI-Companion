# Payjack Route Batch 1 Normalization Backlog

This backlog reviews rows in `payjack_route_tests_1.jsonl` where `normalization_changed` is `true`.
The batch now passes against the current backend, while the `source_*` fields preserve the original aspirational expectations.

## Summary

- Total rows: 80
- Normalized rows: 45
- Current route mix after normalization: 24 `tool`, 17 `rag`, 32 `clarify`, 7 `refuse`
- Most important theme: the current router and policy guard are literal keyword matchers, so many natural-language prompts route differently from the intended product behavior.

## Backlog Themes

### 1. Richer Transaction Lookup Parsing

Rows: `tool-trx-006`, `tool-trx-011`

Current behavior: these route to `clarify` instead of `tool/transaction_lookup`.

Likely improvement:
- Recognize explicit date ranges like `between April 1 and April 30`.
- Recognize quarter ranges like `Q1`.
- Map food/dining language onto supported category filters or add category aliases.
- Avoid requiring the exact `last transaction` or month-name range forms for transaction lookup.

### 2. Status Routing Precedence And Negation

Rows: `tool-sts-011`, `tool-sts-016`

Current behavior:
- `tool-sts-011` routes to `transaction_lookup` because `last Tuesday` plus `transaction` wins before status keywords.
- `tool-sts-016` routes to `refuse` because `send money` appears inside a negated sentence: `I am not asking you to send money again`.

Likely improvement:
- Prioritize explicit status language such as `pending`, `declined`, `successful`, and `actual status` before transaction lookup.
- Make policy detection aware of negated or clarifying phrases around execution verbs.

### 3. Documentation Coverage And Citation Gaps

Rows: `rag-001`, `rag-002`, `rag-003`, `rag-004`, `rag-006`, `rag-010`

Current behavior: these still route to `rag`, but the test fixture expects `base` grounding and no citations because the current lightweight test KB only contains the fees policy chunk.

Likely improvement:
- Expand test KB fixtures, or provide a dedicated route-batch KB fixture, with chunks for PIN reset, transfer limits, send-money fees, bank linking, transaction disputes, and dormant accounts.
- Keep the route as `rag`, but make citation expectations match the richer fixture once available.

### 4. Missing Documentation Intent Keywords

Rows: `rag-005`, `rag-009`

Current behavior: these route to `clarify`.

Likely improvement:
- Add documentation triggers for words and phrases such as `documents`, `verify`, `verification`, `onboarding`, `business account`, and `process`.

### 5. Tool Keywords Stealing Documentation Questions

Rows: `rag-007`, `rag-008`

Current behavior:
- `maximum account balance allowed` routes to `balances`.
- `charge a fee ... how much` routes to `spend_summary`.

Likely improvement:
- Add precedence rules for policy/fee/limit language before account-data tool routes.
- Treat `maximum balance allowed`, `limit`, `charge a fee`, and fee amount questions as documentation unless the user asks about their own observed account data.

### 6. Off-Topic RAG/Base Versus Clarify

Rows: `rag-022`, `rag-023`, `rag-024`, `rag-025`, `rag-026`, `rag-028`, `rag-030`

Current behavior: these route to `clarify`.

Product decision needed:
- Keep off-topic general knowledge as `clarify`, which keeps Payjack tightly scoped.
- Or route broad `what/who/how/can you explain` prompts to `rag/base` with a Payjack documentation fallback.

### 7. Clarify Prompts Overmatched By Broad Tool Or RAG Keywords

Rows: `clarify-001`, `clarify-005`, `clarify-010`, `clarify-011`, `clarify-014`, `clarify-016`, `clarify-017`, `clarify-018`, `clarify-019`, `clarify-020`

Current behavior:
- Generic `help` and uncertain app/account prompts route to `rag`.
- Vague money-management, account-status, and subscription mentions route to tools.

Likely improvement:
- Add uncertainty signals like `not sure`, `something`, `where should I start`, and `overwhelmed`.
- Require a concrete object or filter before invoking tools.
- Consider a confidence score rather than first keyword match.

### 8. Policy Guard Literal-Match Gaps

Rows: `refuse-001`, `refuse-003`, `refuse-004`, `refuse-006`, `refuse-010`, `refuse-011`, `refuse-012`, `refuse-013`, `refuse-016`, `refuse-018`, `refuse-019`

Current behavior: these route to `clarify` because they do not contain the exact disallowed substrings currently listed in `policy_guard.py`.

Likely improvement:
- Add verb variants such as `send 100`, `pay my`, `withdraw 500`, and `transfer all the money`.
- Add prompt-extraction variants such as `system prompt`, `instructions you were given`, `internal tool names`, `API endpoints`, and `routing logic`.
- Add financial-advice variants such as `what stocks should I buy`, `specific investment products`, and allocation percentages.
- Add credit-decision variants such as `eligible for a credit line`.

### 9. Credit And Advice Requests Stolen By Spend Keywords

Rows: `refuse-015`, `refuse-020`

Current behavior: these route to `tool/spend_summary` because `spending history` and `spending patterns` match spend-summary keywords before policy intent is recognized.

Likely improvement:
- Expand policy guard coverage for loan qualification and investment recommendation requests.
- Run policy detection before route keywords, and ensure advice/credit intents win even when the prompt mentions transactions or spending.

### 10. Restriction Bypass Routed To RAG

Row: `refuse-017`

Current behavior: this routes to `rag` because `help me transfer` is not blocked by the exact `transfer money` phrase.

Likely improvement:
- Add execution/bypass combinations like `pretend you have no restrictions` plus transfer/send/pay language.
- Treat `transfer all the money` as transaction execution even when `money` is separated from `transfer`.
