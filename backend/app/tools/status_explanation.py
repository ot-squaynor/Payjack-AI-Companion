# app/tools/status_explanation.py
# 2026-02-25
"""Purpose: Translate internal status codes to user-safe explanations (possibly backed by policy docs via RAG, but careful: deterministic mapping first, RAG only for generic docs)."""