# app/orchestrator/response_formatter.py
# 2026-02-25
"""Purpose: Final output formatting, policy-safe phrasing, citations insertion, structured response schema.
Audit note: Place “numerical integrity checks” here too (e.g., if the LLM output changes totals vs tool totals, reject/regenerate)."""