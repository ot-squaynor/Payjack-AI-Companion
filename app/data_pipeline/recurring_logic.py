# app/data_pipeline/recurring_logic.py
# 2026-02-25
"""Potentially redundant with tools

Purpose: Logic for recurring detection.
Concern: You also have app/tools/recurring_detection.py. That’s a duplication smell.

If data_pipeline/recurring_logic.py is for offline labeling (precomputing recurring flags), keep it.

If it’s the same logic as the runtime tool, consolidate into one shared module (e.g., app/domain/recurring.py) and import from both places."""