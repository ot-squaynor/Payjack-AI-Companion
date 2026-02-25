# app/security/audit_logging.py
# 2026-02-25
"""Purpose: Write structured compliance logs (tool called, user hash, timestamps, refusal events).
Audit note: Ensure logs never include sensitive raw values."""