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

##BRICK 3: Utility functions for S3 client creation, column name standardization, file discovery, and path resolution, to keep the main ingestion logic clean and focused on loading and validating datasets.
def get_s3_client():
    """
    Create and return a boto3 S3 client.

    Why:
    - isolates AWS client creation in one place
    - makes later mocking/testing easier
    - avoids scattering boto3 construction across functions
    """
    try:
        return boto3.client("s3")
    except (BotoCoreError, ClientError) as e:
        raise IngestionError(f"Failed to create S3 client: {e}") from e
    
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
def _join_s3_prefix(*parts: str) -> str:
    """
    Join S3 prefix parts safely without introducing duplicate slashes.

    Example:
        _join_s3_prefix("raw", "transactions") -> "raw/transactions"
    """
    cleaned = [str(p).strip("/").strip() for p in parts if str(p).strip("/").strip()]
    return "/".join(cleaned)


def _resolve_local_dataset_root(source_config: DataSourceConfig, dataset_name: str) -> Path:
    """
    Resolve the local root folder for a dataset.

    Example:
        local_root=data/raw, dataset=transactions
        -> data/raw/transactions
    """
    return Path(source_config.local_root) / dataset_name


def _resolve_s3_dataset_prefix(source_config: DataSourceConfig, dataset_name: str) -> str:
    """
    Resolve the S3 prefix for a dataset.

    Example:
        s3_root_prefix='raw'
        dataset='transactions'
        -> 'raw/transactions'
    """
    return _join_s3_prefix(source_config.s3_root_prefix, dataset_name)


def _validate_source_config(source_config: DataSourceConfig) -> None:
    """
    Validate source configuration before attempting ingestion.

    Why:
    - fail early with a clear message if the source mode is malformed
    """
    mode = source_config.mode.strip().lower()

    if mode not in {"local", "s3"}:
        raise IngestionError(
            f"Unsupported source mode '{source_config.mode}'. Expected 'local' or 's3'."
        )

    if mode == "s3" and not source_config.s3_bucket:
        raise IngestionError("S3 mode requires `s3_bucket` to be set in DataSourceConfig.")

##BRICK 4: Core ingestion functions for listing files in local folders or S3 prefixes, reading file contents as bytes, and loading them into DataFrames, while applying the standardization and validation logic defined earlier.
def list_local_files(folder: Path, recursive: bool = False) -> List[Path]:
    """
    Return supported local files under a dataset folder.

    Args:
        folder:
            Local dataset root, e.g. data/raw/transactions
        recursive:
            If True, search nested subdirectories. This is important for
            partitioned layouts like year/month/day.

    Returns:
        Deterministically sorted list of matching file paths.

    Why:
    - keeps local dev/test mode aligned with S3 behavior
    - supports partitioned datasets without changing downstream logic
    """
    if not folder.exists() or not folder.is_dir():
        return []

    pattern = "**/*" if recursive else "*"
    files = [
        p
        for p in folder.glob(pattern)
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    ]

    return sorted(files, key=lambda p: str(p).lower())


def list_s3_keys(
    bucket: str,
    prefix: str,
    recursive: bool = False,
    s3_client=None,
) -> List[str]:
    """
    List supported S3 object keys under a prefix.

    Args:
        bucket:
            S3 bucket name.
        prefix:
            Dataset prefix, e.g. raw/transactions
        recursive:
            If False, only keep objects directly under the prefix.
            If True, include nested partitioned keys like year/month/day.
        s3_client:
            Optional prebuilt boto3 client.

    Returns:
        Deterministically sorted list of S3 keys.

    AWS calls:
    - list_objects_v2 paginator

    Why:
    - S3 is now a real upstream source of truth
    - transaction data may be partitioned deeply by date
    """
    client = s3_client or get_s3_client()
    normalized_prefix = prefix.strip("/")

    try:
        paginator = client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=bucket, Prefix=normalized_prefix)

        keys: List[str] = []
        for page in page_iterator:
            contents = page.get("Contents", [])
            for obj in contents:
                key = obj["Key"]

                # Skip pseudo-directory placeholders
                if key.endswith("/"):
                    continue

                suffix = Path(key).suffix.lower()
                if suffix not in SUPPORTED_EXTS:
                    continue

                if not recursive:
                    relative = key[len(normalized_prefix):].lstrip("/") if normalized_prefix else key
                    if "/" in relative:
                        continue

                keys.append(key)

        return sorted(keys, key=lambda k: k.lower())

    except (BotoCoreError, ClientError) as e:
        raise IngestionError(
            f"Failed to list S3 objects for s3://{bucket}/{normalized_prefix}: {e}"
        ) from e


def read_local_file_bytes(path: Path) -> bytes:
    """
    Read a local file as raw bytes.

    Why:
    - unifies local and S3 parsing through a shared bytes-based loader
    """
    try:
        return path.read_bytes()
    except OSError as e:
        raise IngestionError(f"Failed to read local file {path}: {e}") from e


def read_s3_object_bytes(bucket: str, key: str, s3_client=None) -> bytes:
    """
    Read an S3 object fully into memory as bytes.

    Args:
        bucket:
            S3 bucket name.
        key:
            S3 object key.
        s3_client:
            Optional prebuilt boto3 client.

    Returns:
        Raw object bytes.

    AWS calls:
    - get_object

    Why:
    - lets downstream parsing be storage-agnostic
    """
    client = s3_client or get_s3_client()

    try:
        response = client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read()
        return body
    except (BotoCoreError, ClientError, KeyError) as e:
        raise IngestionError(f"Failed to read S3 object s3://{bucket}/{key}: {e}") from e

###
# def load_table(path: Path) -> pd.DataFrame:
#     """
#     Load a raw dataset file into a DataFrame.

#     Supported:
#     - CSV
#     - XLS/XLSX (first sheet)
#     - JSON (list[dict] or dict-wrapped list)
#     - JSONL (one JSON object per line)

#     Why:
#     - keeps file-format complexity out of business logic
#     - makes ingestion easy to unit test
#     """
#     if not path.exists():
#         raise IngestionError(f"Missing file: {path}")

#     ext = path.suffix.lower()
#     if ext not in SUPPORTED_EXTS:
#         raise IngestionError(
#             f"Unsupported file type '{ext}' for {path}. Supported: {sorted(SUPPORTED_EXTS)}"
#         )

#     try:
#         if ext == ".csv":
#             # Try BOM-friendly encoding first (common with Excel exports).
#             try:
#                 return pd.read_csv(path, encoding="utf-8-sig")
#             except UnicodeDecodeError:
#                 return pd.read_csv(path, encoding="utf-8")

#         if ext in {".xlsx", ".xls"}:
#             return pd.read_excel(path, sheet_name=0)

#         if ext == ".json":
#             with path.open("r", encoding="utf-8") as f:
#                 obj = json.load(f)

#             if isinstance(obj, list):
#                 return pd.DataFrame(obj)

#             if isinstance(obj, dict):
#                 # Common “wrapped array” patterns
#                 for key in ("data", "items", "records", "rows"):
#                     if key in obj and isinstance(obj[key], list):
#                         return pd.DataFrame(obj[key])

#                 # Fallback: treat dict as a single record
#                 return pd.DataFrame([obj])

#             raise IngestionError(f"Unsupported JSON structure in {path}")

#         if ext == ".jsonl":
#             rows = []
#             with path.open("r", encoding="utf-8") as f:
#                 for i, line in enumerate(f, start=1):
#                     line = line.strip()
#                     if not line:
#                         continue
#                     try:
#                         rows.append(json.loads(line))
#                     except json.JSONDecodeError as e:
#                         raise IngestionError(f"Invalid JSON on line {i} in {path}: {e}") from e
#             return pd.DataFrame(rows)

#         # Should never hit this due to SUPPORTED_EXTS check above
#         raise IngestionError(f"Unhandled file type '{ext}' for {path}")

#     except IngestionError:
#         raise
#     except Exception as e:
#         raise IngestionError(f"Failed to load {path}: {e}") from e


# def discover_latest_file(folder: Path) -> Optional[Path]:
#     """
#     Pick the most recently modified supported file within a dataset folder.

#     Why:
#     - early-stage pipelines often drop a single export file into the folder
#     - reduces configuration friction while iterating
#     """
#     if not folder.exists() or not folder.is_dir():
#         return None

#     candidates = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
#     if not candidates:
#         return None

#     return max(candidates, key=lambda p: p.stat().st_mtime)

##BRICK 5: Shared parsing logic for loading raw bytes into DataFrames, which can be used by both local file ingestion and S3 object ingestion, to keep the core parsing logic consistent and testable regardless of the source.
def load_table_from_bytes(file_bytes: bytes, suffix: str) -> pd.DataFrame:
    """
    Parse raw bytes into a pandas DataFrame based on file extension.

    Supported:
    - .csv
    - .xlsx / .xls
    - .json
    - .jsonl

    Why:
    - keeps parsing logic shared between local files and S3 objects
    - makes ingestion storage-agnostic once bytes are loaded
    """
    ext = suffix.lower().strip()
    if ext not in SUPPORTED_EXTS:
        raise IngestionError(f"Unsupported file type '{ext}'. Supported: {sorted(SUPPORTED_EXTS)}")

    try:
        if ext == ".csv":
            try:
                return pd.read_csv(BytesIO(file_bytes), encoding="utf-8-sig")
            except UnicodeDecodeError:
                return pd.read_csv(BytesIO(file_bytes), encoding="utf-8")

        if ext in {".xlsx", ".xls"}:
            return pd.read_excel(BytesIO(file_bytes), sheet_name=0)

        if ext == ".json":
            try:
                obj = json.loads(file_bytes.decode("utf-8"))
            except UnicodeDecodeError:
                obj = json.loads(file_bytes.decode("utf-8-sig"))

            if isinstance(obj, list):
                return pd.DataFrame(obj)

            if isinstance(obj, dict):
                for key in ("data", "items", "records", "rows", "transactions", "accounts"):
                    if key in obj and isinstance(obj[key], list):
                        return pd.DataFrame(obj[key])

                return pd.DataFrame([obj])

            raise IngestionError("Unsupported JSON structure")

        if ext == ".jsonl":
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = file_bytes.decode("utf-8-sig")

            rows = []
            for i, line in enumerate(text.splitlines(), start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as e:
                    raise IngestionError(f"Invalid JSON on line {i}: {e}") from e

            return pd.DataFrame(rows)

        raise IngestionError(f"Unhandled file type '{ext}'")

    except IngestionError:
        raise
    except Exception as e:
        raise IngestionError(f"Failed to parse bytes as '{ext}': {e}") from e


def load_many_tables(
    sources: Iterable[Tuple[str, bytes]],
) -> pd.DataFrame:
    """
    Load and concatenate many tabular sources into a single DataFrame.

    Args:
        sources:
            Iterable of (source_name, file_bytes), where source_name is used
            to infer the suffix and improve error messages/logging.

    Behavior:
    - Parses each source independently
    - Adds a `_source_name` lineage column for traceability
    - Concatenates all parsed tables row-wise

    Why:
    - partitioned daily/monthly/yearly transaction exports need one combined table
    - multi-file datasets should look like one logical dataset downstream
    """
    frames: List[pd.DataFrame] = []

    for source_name, file_bytes in sources:
        suffix = Path(source_name).suffix.lower()
        if suffix not in SUPPORTED_EXTS:
            logger.debug("Skipping unsupported source during multi-load: %s", source_name)
            continue

        logger.info("Loading tabular source: %s", source_name)
        df = load_table_from_bytes(file_bytes, suffix=suffix)
        df = df.copy()
        df["_source_name"] = source_name
        frames.append(df)

    if not frames:
        raise IngestionError("No supported tabular sources were available to load")

    # sort=False preserves all columns across heterogeneous batches
    return pd.concat(frames, ignore_index=True, sort=False)

##BRICK 6
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
            series = out[c].astype(str).str.replace(",", "", regex=False)
            series = series.str.replace("£", "", regex=False).str.replace("$", "", regex=False)
            out[c] = pd.to_numeric(series, errors="coerce")
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
def deduplicate_rows(
    df: pd.DataFrame,
    subset: Optional[str] = None,
) -> pd.DataFrame:
    """
    Drop duplicate rows using an optional key column.

    Args:
        df:
            Input DataFrame.
        subset:
            Column name to use as the dedupe key. If None, returns the DataFrame unchanged.

    Why:
    - partitioned exports may overlap across re-runs or partial backfills
    - transaction_id/account_id/product_id/item_id are natural first-pass dedupe keys
    """
    if not subset:
        return df

    if subset not in df.columns:
        logger.warning("Dedupe key '%s' not found in columns; skipping dedupe", subset)
        return df

    before = len(df)
    out = df.drop_duplicates(subset=[subset], keep="first")
    dropped = before - len(out)

    if dropped:
        logger.info("Dropped %s duplicate rows using dedupe key '%s'", dropped, subset)

    return out

##BRICK 7: The main ingestion function that ties everything together, applying the configuration and specifications to load datasets from the specified source, standardize and validate them, and return a clean DataFrame for downstream processing.
def ingest_dataset(
    spec: DatasetSpec,
    source_config: DataSourceConfig,
    s3_client=None,
) -> pd.DataFrame:
    """
    Ingest one logical dataset from either local storage or S3.

    Flow:
    - validate source configuration
    - discover matching files/objects
    - load one or many tables
    - standardize column names
    - coerce types
    - validate required columns
    - drop fully empty rows
    - deduplicate where configured

    Args:
        spec:
            Dataset contract and loading behavior.
        source_config:
            Storage location config (local or s3).
        s3_client:
            Optional injected boto3 S3 client for reuse or testing.

    Returns:
        Canonical ingested DataFrame for the dataset.
    """
    _validate_source_config(source_config)
    mode = source_config.mode.strip().lower()

    source_items: List[Tuple[str, bytes]] = []

    if mode == "local":
        dataset_root = _resolve_local_dataset_root(source_config, spec.name)
        file_paths = list_local_files(dataset_root, recursive=spec.recursive)

        if not file_paths:
            raise IngestionError(f"[{spec.name}] No supported local files found in {dataset_root}")

        if not spec.multi_file:
            file_paths = file_paths[:1]

        for path in file_paths:
            logger.info("Reading local dataset source for '%s': %s", spec.name, path)
            file_bytes = read_local_file_bytes(path)
            source_items.append((str(path), file_bytes))

    elif mode == "s3":
        bucket = source_config.s3_bucket
        if not bucket:
            raise IngestionError(f"[{spec.name}] S3 mode requires a bucket name")

        dataset_prefix = _resolve_s3_dataset_prefix(source_config, spec.name)
        keys = list_s3_keys(
            bucket=bucket,
            prefix=dataset_prefix,
            recursive=spec.recursive,
            s3_client=s3_client,
        )

        if not keys:
            raise IngestionError(f"[{spec.name}] No supported S3 objects found under s3://{bucket}/{dataset_prefix}")

        if not spec.multi_file:
            keys = keys[:1]

        for key in keys:
            logger.info("Reading S3 dataset source for '%s': s3://%s/%s", spec.name, bucket, key)
            file_bytes = read_s3_object_bytes(bucket=bucket, key=key, s3_client=s3_client)
            source_items.append((key, file_bytes))

    else:
        raise IngestionError(f"[{spec.name}] Unsupported source mode '{source_config.mode}'")

    # Parse source(s)
    if spec.multi_file:
        df = load_many_tables(source_items)
    else:
        source_name, file_bytes = source_items[0]
        suffix = Path(source_name).suffix.lower()
        df = load_table_from_bytes(file_bytes, suffix=suffix)
        df = df.copy()
        df["_source_name"] = source_name

    # Canonicalize schema before validation
    df = standardize_columns(df)

    # Conservative type coercion
    df = _coerce_dates(df, spec.date_columns)
    df = _coerce_numeric(df, spec.numeric_columns)
    df = _coerce_strings(df, spec.string_columns)

    # Minimum schema enforcement
    validate_required_columns(df, spec.required_columns, dataset_name=spec.name)

    # Minimal cleanup
    df = df.dropna(how="all")

    # Dedupe if configured
    df = deduplicate_rows(df, subset=spec.dedupe_key)

    logger.info(
        "Ingested dataset '%s' with %s rows and %s columns",
        spec.name,
        len(df),
        len(df.columns),
    )

    return df

##BRICK 8: A higher-level function to load all datasets defined in the specifications, applying the ingestion logic to each and returning a bundle of DataFrames, along with a utility to write these intermediate results to disk for reproducibility and faster iteration.
def load_raw_bundle(
    source_config: DataSourceConfig,
    strict: bool = True,
    s3_client=None,
) -> Dict[str, pd.DataFrame]:
    """
    Load all datasets defined in `_specs()` into a consistent bundle.

    Args:
        source_config:
            Local or S3 source configuration.
        strict:
            - True: raise on any dataset failure
            - False: skip failed datasets and continue
        s3_client:
            Optional injected boto3 S3 client.

    Returns:
        Dict[str, pd.DataFrame] mapping dataset name -> ingested DataFrame.
    """
    _validate_source_config(source_config)

    bundle: Dict[str, pd.DataFrame] = {}

    for name, spec in _specs().items():
        try:
            bundle[name] = ingest_dataset(spec=spec, source_config=source_config, s3_client=s3_client)
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
    Persist ingestion outputs as local intermediate artifacts.

    Why:
    - reproducibility
    - faster downstream iteration
    - clean seam between ingestion and normalization

    Supported formats:
    - parquet
    - csv
    - jsonl
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
    logging.basicConfig(level=logging.INFO)

    # Default local run for quick development usage.
    source = DataSourceConfig(mode="local", local_root=Path("data/raw"))

    bundle = load_raw_bundle(source_config=source, strict=False)
    written = write_intermediate(bundle=bundle, out_dir=Path("data/processed"), fmt="parquet")

    logger.info("Wrote ingestion intermediates: %s", {k: str(v) for k, v in written.items()})
# Needs a little more work to be a full standalone script (e.g., command-line args for raw/processed paths, format), but this is the core logic for ingestion.
