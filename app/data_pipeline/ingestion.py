# app/data_pipeline/ingestion.py
# 2026-02-25
"""Purpose: Pull docs / reference data into your system (KB docs, maybe synthetic datasets, maybe staging exports).
Risk: In-prod ingestion inside the chat service increases blast radius.
Best practice: Run as separate ECS task / scheduled job / CI pipeline step."""

"""
Ingestion layer for raw PayJack/OrangeTech-style datasets.

Goal:
- Load raw datasets from data/raw/* into canonical pandas DataFrames
- Standardize column names early (aliases, casing, whitespace)
- Perform boundary validation + type coercion (dates, numerics, IDs)
- Return a consistent bundle for downstream stages:
    normalization -> category_mapping -> recurring_logic -> quality_checks

This module intentionally does NOT apply business rules (that's normalization).
"""
#IMPORTS:
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple, Iterable # for type hints
import json
import logging # Ingestion needs strong observability: “what file did I load”, “why did it fail”.
import os
import pandas as pd # pandas is a common choice for tabular data manipulation, but we could swap in something else if needed.

# #CONFIG:
# RAW_DATA_DIR = Path("data/raw") # Base directory for raw datasets. In a real system, this might be an S3 bucket or database connection string.
# # Set up logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

#CONSTANTS:
SUPPORTED_EXTS = {".json", ".jsonl", ".csv", ".xlsx", ".xls"}# We can easily add more formats later (e.g., Parquet, Avro) if needed.
COLUMN_ALIASES: Dict[str, str]
