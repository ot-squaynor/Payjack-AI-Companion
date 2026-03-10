# app/data_pipeline/normalization.py
# 2026-02-25
"""Purpose: Standardize incoming data (doc cleaning, chunk formatting, transaction category mapping if you do any).
Key constraint: If it touches transaction data, it must remain deterministic and auditable."""

"""Normalization is where raw-but-consistent data becomes canonical business-ready data. In practice:

enforce consistent currencies/amount signs

standardize merchant strings

normalize categories into a stable taxonomy

fill/derive missing fields (direction, day/month, ISO codes)

output normalized frames that the tools and recurring detection can trust

Non-goal: deep integrity enforcement (that’s quality_checks.py). Normalization should be a pure transformation layer, not a gatekeeper. If data is weird but processable, normalize it rather than rejecting it."""

"""CURRENCY_ALIASES: dict[str, str]
e.g., "GHC" -> "GHS", "cedi" -> "GHS", "gbp" -> "GBP" """
