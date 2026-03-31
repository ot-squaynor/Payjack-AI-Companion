# app/llm/autoregressive/model_selector.py
# 2026-02-25
"""Purpose: Choose model by intent/context (e.g., cheaper model for simple formatting; stronger model for complex multi-tool explanation).
Audit note: Keep selection deterministic and logged (for audit + cost control)."""