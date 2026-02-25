# app/data_pipeline/ingestion.py
# 2026-02-25
"""Purpose: Pull docs / reference data into your system (KB docs, maybe synthetic datasets, maybe staging exports).
Risk: In-prod ingestion inside the chat service increases blast radius.
Best practice: Run as separate ECS task / scheduled job / CI pipeline step."""