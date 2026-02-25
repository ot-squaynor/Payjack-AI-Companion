# app/data_pipeline/quality_checks.py
# 2026-02-25
"""Purpose: Gatekeeping (schema validation, missing fields, drift detection, doc quality, duplicate chunks).
This is a big win for fintech: it prevents bad KB content from poisoning retrieval."""