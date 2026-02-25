# app/rag/evaluation.py
# 2026-02-25
"""Integral (but may belong outside runtime)

Purpose: Measure retrieval performance (precision@k, hit rate, citation correctness).
Audit note: For production image size, you might move heavy eval utilities out of app/ into /evaluation/ and keep only minimal hooks in runtime. But keeping the module isn’t wrong if it’s lightweight."""