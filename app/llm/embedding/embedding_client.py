# app/llm/embedding/embedding_client.py
# 2026-02-25
#wrapper to call embedding model.
"""Purpose: Single audited embedding client wrapper.
Must include:

Timeouts/retries (carefully), request IDs, token/cost capture.

Guardrail hooks: PII redaction + policy guard before calling, and output checks after.

Streaming optional."""
#Audit note: Embedding code should never touch sensitive PII. If you embed docs only, good. If you ever embed user data, that’s a major compliance decision. 
# If you do embed user data, you must have strong PII redaction and guardrails in place, and it must be fully auditable.