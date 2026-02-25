# app/llm/embedding/vector_encoder.py
# 2026-02-25
#chunk -> embedding pipeline logic (batching, normalization)
"""Purpose: Encode text into vector embeddings.
Audit note: Must be deterministic and logged (for audit + cost control)."""