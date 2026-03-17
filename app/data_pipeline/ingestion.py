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
##BRICK 1: Imports and configuration, including logging setup and constants for supported file types and column aliases.
"""
S3-aware ingestion layer for raw structured datasets.

Responsibilities:
- Load raw dataset files from either:
    1) local filesystem
    2) S3 bucket + prefix
- Support partitioned datasets (e.g. transactions by year/month/day)
- Parse CSV / XLSX / JSON / JSONL into pandas DataFrames
- Standardize column names into canonical internal names
- Apply light type coercion (dates, numerics, strings)
- Validate minimum required columns
- Concatenate multi-file datasets
- Deduplicate rows where configured
- Return a consistent bundle for downstream stages

Non-goals:
- No business normalization logic (normalization.py)
- No advanced integrity enforcement (quality_checks.py)
- No LLM/orchestrator/tool logic
"""
#IMPORTS:
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

import boto3
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError
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
@dataclass(frozen=True)
class DataSourceConfig:
    """
    Describes where raw datasets should be loaded from.

    mode:
        - "local": read from local filesystem under local_root
        - "s3": read from S3 bucket + optional root prefix

    Examples:
        local:
            DataSourceConfig(mode="local", local_root=Path("data/raw"))

        s3:
            DataSourceConfig(
                mode="s3",
                s3_bucket="fidelity-raw-data",
                s3_root_prefix="raw/"
            )
    """
    mode: str = "local"
    local_root: Path = Path("data/raw")
    s3_bucket: Optional[str] = None
    s3_root_prefix: str = ""
@dataclass(frozen=True)
class DatasetSpec:
    """
    Describes the ingestion contract and loading behavior for one dataset.

    required_columns:
        Minimum columns that must exist after column standardization.

    recursive:
        Whether nested directories / prefixes should be searched.

    multi_file:
        Whether all matched files should be loaded and concatenated.

    dedupe_key:
        Optional subset column used to drop duplicate rows after load.
        Useful for partitioned transaction exports.
    """
    name: str
    required_columns: Tuple[str, ...]
    date_columns: Tuple[str, ...] = ()
    numeric_columns: Tuple[str, ...] = ()
    string_columns: Tuple[str, ...] = ()
    recursive: bool = False
    multi_file: bool = False
    dedupe_key: Optional[str] = None    
##BRICK 2: Dataset specifications for each expected dataset, including required columns, type hints for coercion, and loading behavior (e.g., recursive search, multi-file concatenation, deduplication keys).

# Supported raw file extensions for structured ingestion.
SUPPORTED_EXTS = {".json", ".jsonl", ".csv", ".xlsx", ".xls"}

# Canonical column aliases.
# These map common raw/exported header variants -> stable internal names.
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

    # Monetary values
    "amt": "amount",
    "amount": "amount",
    "ccy": "currency",
    "currency": "currency",

    # Textual descriptors
    "merchantname": "merchant",
    "merchant": "merchant",
    "narration": "description",
    "description": "description",
    "category": "category",

    # Accounts
    "accountname": "account_name",
    "account_name": "account_name",
    "accounttype": "account_type",
    "account_type": "account_type",

    # Products
    "productid": "product_id",
    "product_id": "product_id",
    "productname": "product_name",
    "product_name": "product_name",
    "producttype": "product_type",
    "product_type": "product_type",

    # Fees / limits / metadata
    "type": "item_type",
    "item_type": "item_type",
    "value": "value",
    "unit": "unit",
    "notes": "notes",
    "key": "key",
    "val": "value",
    "source": "source",
}

def _specs() -> Dict[str, DatasetSpec]:
    """
    Central ingestion contract registry.

    Notes:
    - transactions are configured for recursive, multi-file loading
      because they may be partitioned by year/month/day in S3 or locally.
    - other datasets are left flexible enough to support either single-file
      or batched exports later if needed.
    """
    return {
        "transactions": DatasetSpec(
            name="transactions",
            required_columns=("transaction_id", "account_id", "amount", "currency", "timestamp"),
            date_columns=("timestamp",),
            numeric_columns=("amount",),
            string_columns=("transaction_id", "account_id", "currency", "merchant", "category", "description"),
            recursive=True,
            multi_file=True,
            dedupe_key="transaction_id",
        ),
        "accounts": DatasetSpec(
            name="accounts",
            required_columns=("account_id", "account_name"),
            string_columns=("account_id", "account_name", "account_type", "currency"),
            recursive=True,
            multi_file=True,
            dedupe_key="account_id",
        ),
        "fees_and_limits": DatasetSpec(
            name="fees_and_limits",
            required_columns=("item_id", "item_type", "value"),
            numeric_columns=("value",),
            string_columns=("item_id", "item_type", "unit", "notes"),
            recursive=True,
            multi_file=True,
            dedupe_key="item_id",
        ),
        "products": DatasetSpec(
            name="products",
            required_columns=("product_id", "product_name"),
            string_columns=("product_id", "product_name", "product_type"),
            recursive=True,
            multi_file=True,
            dedupe_key="product_id",
        ),
        "metadata": DatasetSpec(
            name="metadata",
            required_columns=("key", "value"),
            string_columns=("key", "value", "source"),
            recursive=True,
            multi_file=True,
            dedupe_key=None,  # metadata keys may legitimately repeat across sources
        ),
    }

##BRICK 3: Constants and helper functions for column standardization, including a mapping of common “messy” header variants to canonical names.

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

##BRICK 4: Ingestion function to load a raw dataset file into a DataFrame, with support for multiple formats and error handling.
def load_table(path: Path) -> pd.DataFrame:
    """
    Load a raw dataset file into a DataFrame.

    Supported:
    - CSV
    - XLS/XLSX (first sheet)
    - JSON (list[dict] or dict-wrapped list)
    - JSONL (one JSON object per line)

    Why:
    - keeps file-format complexity out of business logic
    - makes ingestion easy to unit test
    """
    if not path.exists():
        raise IngestionError(f"Missing file: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise IngestionError(
            f"Unsupported file type '{ext}' for {path}. Supported: {sorted(SUPPORTED_EXTS)}"
        )

    try:
        if ext == ".csv":
            # Try BOM-friendly encoding first (common with Excel exports).
            try:
                return pd.read_csv(path, encoding="utf-8-sig")
            except UnicodeDecodeError:
                return pd.read_csv(path, encoding="utf-8")

        if ext in {".xlsx", ".xls"}:
            return pd.read_excel(path, sheet_name=0)

        if ext == ".json":
            with path.open("r", encoding="utf-8") as f:
                obj = json.load(f)

            if isinstance(obj, list):
                return pd.DataFrame(obj)

            if isinstance(obj, dict):
                # Common “wrapped array” patterns
                for key in ("data", "items", "records", "rows"):
                    if key in obj and isinstance(obj[key], list):
                        return pd.DataFrame(obj[key])

                # Fallback: treat dict as a single record
                return pd.DataFrame([obj])

            raise IngestionError(f"Unsupported JSON structure in {path}")

        if ext == ".jsonl":
            rows = []
            with path.open("r", encoding="utf-8") as f:
                for i, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        raise IngestionError(f"Invalid JSON on line {i} in {path}: {e}") from e
            return pd.DataFrame(rows)

        # Should never hit this due to SUPPORTED_EXTS check above
        raise IngestionError(f"Unhandled file type '{ext}' for {path}")

    except IngestionError:
        raise
    except Exception as e:
        raise IngestionError(f"Failed to load {path}: {e}") from e


def discover_latest_file(folder: Path) -> Optional[Path]:
    """
    Pick the most recently modified supported file within a dataset folder.

    Why:
    - early-stage pipelines often drop a single export file into the folder
    - reduces configuration friction while iterating
    """
    if not folder.exists() or not folder.is_dir():
        return None

    candidates = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
    if not candidates:
        return None

    return max(candidates, key=lambda p: p.stat().st_mtime)

##BRICK 5: Type coercion and validation functions to ensure that the ingested DataFrame has the expected types for date, numeric, and string columns, and that required columns are present.
def _coerce_dates(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    """
    Coerce selected columns to UTC datetime.

    Why:
    - downstream recurring detection and time filtering must not depend on string dates
    """
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_datetime(out[c], errors="coerce", utc=True)
    return out


def _coerce_numeric(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    """
    Convert selected columns to numeric (float/int).

    Handles common formatting issues:
    - commas: "1,234.50"
    - currency symbols: "£12.00" "$12.00"

    Why:
    - tools and summaries must not do math on strings
    """
    out = df.copy()
    for c in cols:
        if c in out.columns:
            s = out[c].astype(str).str.replace(",", "", regex=False)
            s = s.str.replace("£", "", regex=False).str.replace("$", "", regex=False)
            out[c] = pd.to_numeric(s, errors="coerce")
    return out


def _coerce_strings(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    """
    Force selected columns to pandas string dtype.

    Why:
    - IDs should not accidentally become floats (e.g., 00123 -> 123.0)
    """
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].astype("string")
    return out


def validate_required_columns(df: pd.DataFrame, required: Iterable[str], dataset_name: str) -> None:
    """
    Fail-fast if required columns are missing.

    Why:
    - without the minimum set, downstream stages will break in harder-to-debug ways
    """
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise IngestionError(
            f"[{dataset_name}] Missing required columns: {missing}. "
            f"Present columns: {sorted(df.columns.tolist())}"
        )


def ingest_dataset(folder: Path, spec: DatasetSpec) -> pd.DataFrame:
    """
    Load + standardize + coerce + validate a single dataset from its folder.

    Folder convention:
        data/raw/<dataset_name>/
            <export>.csv|json|xlsx|jsonl

    Why:
    - provides a single consistent ingestion operation for all datasets
    """
    file_path = discover_latest_file(folder)
    if file_path is None:
        raise IngestionError(f"[{spec.name}] No supported files found in {folder}")

    logger.info("Ingesting '%s' from %s", spec.name, file_path)

    df = load_table(file_path)
    df = standardize_columns(df)

    # Coerce types conservatively based on spec hints
    df = _coerce_dates(df, spec.date_columns)
    df = _coerce_numeric(df, spec.numeric_columns)
    df = _coerce_strings(df, spec.string_columns)

    validate_required_columns(df, spec.required_columns, dataset_name=spec.name)

    # Minimal cleanup: remove completely empty rows
    df = df.dropna(how="all")

    return df

##BRICK 6
def load_raw_bundle(
    raw_root: Path | str = Path("data/raw"),
    strict: bool = True,
) -> Dict[str, pd.DataFrame]:
    """
    Load all datasets defined in `_specs()` into a consistent bundle.

    Args:
        raw_root: root directory containing per-dataset subfolders
        strict:
            - True: raise on any missing/invalid dataset (best for CI, production-like runs)
            - False: skip datasets that fail to load (best for early local iteration)

    Returns:
        dict mapping dataset_name -> DataFrame
    """
    raw_root = Path(raw_root)
    bundle: Dict[str, pd.DataFrame] = {}

    for name, spec in _specs().items():
        folder = raw_root / name
        try:
            bundle[name] = ingest_dataset(folder, spec)
        except IngestionError as e:
            if strict:
                raise
            logger.warning("Skipping dataset '%s' due to ingestion error: %s", name, e)

    return bundle


def write_intermediate(
    bundle: Mapping[str, pd.DataFrame],
    out_dir: Path | str = Path("data/processed"),
    fmt: str = "parquet",
) -> Dict[str, Path]:
    """
    Persist ingestion outputs as intermediate artifacts.

    Why:
    - reproducibility (same inputs -> same intermediate files)
    - speed (downstream stages can start from processed files)
    - clean seam: ingestion boundary vs normalization/business logic

    Supported formats:
    - parquet (recommended)
    - csv
    - jsonl

    Returns:
        dict mapping dataset_name -> written file path
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fmt = fmt.lower().strip()
    written: Dict[str, Path] = {}

    for name, df in bundle.items():
        if fmt == "parquet":
            path = out_dir / f"{name}.parquet"
            df.to_parquet(path, index=False)
        elif fmt == "csv":
            path = out_dir / f"{name}.csv"
            df.to_csv(path, index=False)
        elif fmt == "jsonl":
            path = out_dir / f"{name}.jsonl"
            df.to_json(path, orient="records", lines=True, force_ascii=False)
        else:
            raise IngestionError(f"Unsupported intermediate format '{fmt}'")

        written[name] = path

    return written


if __name__ == "__main__":
    # Optional: allows quick manual runs like:
    #   python -m app.data_pipeline.ingestion
    logging.basicConfig(level=logging.INFO)

    bundle = load_raw_bundle(Path("data/raw"), strict=False)
    paths = write_intermediate(bundle, Path("data/processed"), fmt="parquet")

    logger.info("Wrote ingestion intermediates: %s", {k: str(v) for k, v in paths.items()})
# Needs a little more work to be a full standalone script (e.g., command-line args for raw/processed paths, format), but this is the core logic for ingestion.