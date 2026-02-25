# app/api/routes_chat.py
# 2026-02-25
"""Purpose: /chat endpoint (or similar), request validation, session handling, calling orchestrator.
Must enforce:

Auth context is present (user identity, roles, tenant).

Request schema validation (no raw dicts).

Rate limiting / size limits (anti prompt-bomb).

No direct DB calls; no direct Bedrock calls """