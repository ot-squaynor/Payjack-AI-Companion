# app/llm/autoregressive/streaming_handler.py
# 2026-02-25
"""Optional but valuable

Purpose: Stream tokens to client for UX.
Audit note: Must still preserve audit logging (don’t lose content or tool traces)."""