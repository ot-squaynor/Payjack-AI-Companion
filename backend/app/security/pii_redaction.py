# app/security/pii_redaction.py
# 2026-02-25
"""Purpose: Scrub user input + tool outputs before any LLM call, and scrub LLM output before returning.
Audit note: Keep deterministic patterns, unit tests, and “fail closed” behavior."""