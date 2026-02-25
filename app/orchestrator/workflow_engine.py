# app/orchestrator/workflow_engine.py
# 2026-02-25
"""Purpose: Defines the step graph: “call tool → validate output → maybe call retriever → compose response”.
Key requirement: Deterministic verification: LLM must not alter numbers returned by tools. structure supports this; enforce it here."""