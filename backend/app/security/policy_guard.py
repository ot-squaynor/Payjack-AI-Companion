# app/security/policy_guard.py
# 2026-02-25
"""Purpose: Block disallowed intents (execute transactions, provide financial advice, credit decisions, prompt extraction).
Audit note: Should run early (before tool calls) and also on output."""