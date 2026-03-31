# app/llm/embedding/similarity_utils.py
# 2026-02-25
#distance metrics, thresholding, rerank helpers.
"""Purpose: Utilities for computing similarity between embeddings.
Audit note: Must be deterministic and logged (for audit + cost control)."""