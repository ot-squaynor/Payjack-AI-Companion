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
#SUPPORTED_EXTS = {".json", ".jsonl", ".csv", ".xlsx", ".xls"}# We can easily add more formats later (e.g., Parquet, Avro) if needed.
#COLUMN_ALIASES: Dict[str, str] # Maps common variations of column names to a standardized name. This helps ensure consistency across datasets.

#
logger = logging.getLogger(__name__) # Use a module-level logger for better control over logging output.

#CLASS DEFINITIONS:
# Custom exception for ingestion errors, to keep error handling clean and specific.
class IngestionError(RuntimeError):
    """
    Raised when raw dataset loading/validation fails.

    Why a custom exception:
    - allows callers (scripts/tests) to catch ingestion-specific failures
    - keeps tracebacks clean and failure reasons explicit
    """
    pass

# Data class to define the expected structure of each dataset. This serves as a contract for what the ingestion function should produce.
@dataclass(frozen=True)
class DatasetSpec:
    """
    Minimal ingestion contract for a dataset.

    Keep `required_columns` intentionally small:
    - ingestion should accept messy but usable exports
    - stricter constraints belong in `quality_checks.py`
    """
    name: str
    required_columns: Tuple[str, ...]
    date_columns: Tuple[str, ...] = ()
    numeric_columns: Tuple[str, ...] = ()
    string_columns: Tuple[str, ...] = ()


def _specs() -> Dict[str, DatasetSpec]:
    """
    Single source of truth for ingestion expectations.

    Notes:
    - These are canonical *post-standardization* names.
    - Expand gradually as your real exports stabilize.
    """
    return {
        "transactions": DatasetSpec(
            name="transactions",
            required_columns=("transaction_id", "account_id", "amount", "currency", "timestamp"),
            date_columns=("timestamp",),
            numeric_columns=("amount",),
            string_columns=("transaction_id", "account_id", "currency", "merchant", "category", "description"),
        ),
        "accounts": DatasetSpec(
            name="accounts",
            required_columns=("account_id", "account_name"),
            string_columns=("account_id", "account_name", "account_type", "currency"),
        ),
        "fees_and_limits": DatasetSpec(
            name="fees_and_limits",
            required_columns=("item_id", "item_type", "value"),
            numeric_columns=("value",),
            string_columns=("item_id", "item_type", "unit", "notes"),
        ),
        "products": DatasetSpec(
            name="products",
            required_columns=("product_id", "product_name"),
            string_columns=("product_id", "product_name", "product_type"),
        ),
        "metadata": DatasetSpec(
            name="metadata",
            required_columns=("key", "value"),
            string_columns=("key", "value", "source"),
        ),
    }
# Supported raw file extensions for ingestion
SUPPORTED_EXTS = {".json", ".jsonl", ".csv", ".xlsx", ".xls"}

# Maps common “messy” headers -> canonical headers.
# Extend this over time as you see real export variants.
COLUMN_ALIASES: Dict[str, str] = {
    # Transaction identifiers
    "id": "transaction_id",
    "tx_id": "transaction_id",
    "transactionid": "transaction_id",
    "transaction_id": "transaction_id",

    # Account identifiers
    "accountid": "account_id",
    "acct_id": "account_id",
    "account_id": "account_id",

    # Timestamps
    "date": "timestamp",
    "datetime": "timestamp",
    "created_at": "timestamp",
    "timestamp": "timestamp",

    # Money
    "amt": "amount",
    "amount": "amount",
    "ccy": "currency",
    "currency": "currency",

    # Descriptors
    "merchantname": "merchant",
    "merchant": "merchant",
    "narration": "description",
    "description": "description",
    "category": "category",

    # Accounts
    "accountname": "account_name",
    "account_name": "account_name",

    # Products
    "productid": "product_id",
    "product_id": "product_id",
    "productname": "product_name",
    "product_name": "product_name",

    # Fees/limits/metadata style tables
    "type": "item_type",
    "item_type": "item_type",
    "value": "value",
    "unit": "unit",
    "notes": "notes",
    "key": "key",
    "val": "value",
}


def standardize_column_name(col: str) -> str:
    """
    Convert a raw column label into a canonical column label.

    Steps:
    - strip whitespace
    - lowercase
    - replace separators with underscores
    - remove non-alphanumeric/underscore characters
    - apply alias mapping for known variants

    Why:
    - real exports are inconsistent; canonical schema must still work reliably
    """
    if col is None:
        return col

    c = str(col).strip().lower()
    c = c.replace(" ", "_").replace("-", "_").replace("/", "_")
    while "__" in c:
        c = c.replace("__", "_")

    # Remove most punctuation safely
    c = "".join(ch for ch in c if ch.isalnum() or ch == "_")

    return COLUMN_ALIASES.get(c, c)


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy of the DataFrame with standardized canonical column names.
    """
    out = df.copy()
    out.columns = [standardize_column_name(c) for c in out.columns]
    return out