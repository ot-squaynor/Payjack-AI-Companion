# app/data_pipeline/normalization.py
# 2026-02-25
"""Purpose: Standardize incoming data (doc cleaning, chunk formatting, transaction category mapping if you do any).
Key constraint: If it touches transaction data, it must remain deterministic and auditable."""