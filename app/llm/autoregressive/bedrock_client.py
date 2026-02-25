# app/llm/autoregressive/bedrock_client.py
# 2026-02-25
"""Purpose: Single audited Bedrock invocation wrapper.
Must include:

Timeouts/retries (carefully), request IDs, token/cost capture.

Guardrail hooks: PII redaction + policy guard before calling, and output checks after.

Streaming optional."""