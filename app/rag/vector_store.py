# app/rag/vector_store.py
# 2026-02-25
"""Purpose: Abstraction over vector DB (Chroma locally, OpenSearch/pgvector/Bedrock KB in prod, etc.).
Audit note: Interface design matters: upsert, query, delete_by_namespace, health."""