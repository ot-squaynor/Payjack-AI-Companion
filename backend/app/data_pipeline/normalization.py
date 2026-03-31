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


"""
Normalization layer for ingested datasets.

Responsibilities:
- Convert ingested-but-messy data into canonical business-ready data
- Standardize currencies, merchant strings, categories, and account/product fields
- Derive helper fields used later by recurring logic, tools, and QC
- Return a normalized bundle of pandas DataFrames

Non-goals:
- No raw file loading (handled by ingestion.py)
- No deep integrity enforcement (handled by quality_checks.py)
- No LLM/AWS/tool/runtime orchestration logic
"""
##BRICK 1: Define NormalizationConfig dataclass for configurable normalization behavior.
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, Mapping, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class NormalizationError(RuntimeError):
    """
    Raised when a normalization step fails in a pipeline-specific way.

    Why a custom exception:
    - distinguishes normalization failures from ingestion failures
    - keeps pipeline error handling cleaner in scripts/tests
    """


@dataclass(frozen=True)
class NormalizationConfig:
    """
    Configurable normalization behavior.

    Keep policy choices here rather than burying them in transforms.
    """
    default_currency: Optional[str] = None
    drop_invalid_rows: bool = False
    timezone_utc: bool = True
    derive_transaction_direction: bool = True

##BRICK 2: Define normalization constants and regex patterns for standardizing currencies, categories, item types, and account types.
# Currency normalization aliases.
# Extend as you encounter real source-system variants.
CURRENCY_ALIASES: Dict[str, str] = {
    "ghs": "GHS",
    "ghc": "GHS",
    "cedi": "GHS",
    "cedis": "GHS",
    "ghana cedi": "GHS",
    "ghana cedis": "GHS",
    "gbp": "GBP",
    "pound": "GBP",
    "pounds": "GBP",
    "sterling": "GBP",
    "usd": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
}

# Light category cleanup aliases.
# This is only the baseline normalization layer.
# Deeper domain taxonomy belongs in category_mapping.py.
CATEGORY_ALIASES: Dict[str, str] = {
    "groceries": "groceries",
    "grocery": "groceries",
    "supermarket": "groceries",
    "transport": "transport",
    "transportation": "transport",
    "fuel": "transport",
    "ride": "transport",
    "rides": "transport",
    "salary": "income",
    "income": "income",
    "wages": "income",
    "bills": "bills",
    "bill": "bills",
    "utilities": "bills",
    "shopping": "shopping",
    "retail": "shopping",
    "food": "food_and_drink",
    "restaurant": "food_and_drink",
    "restaurants": "food_and_drink",
    "dining": "food_and_drink",
    "transfer": "transfers",
    "transfers": "transfers",
    "bank transfer": "transfers",
    "cash withdrawal": "cash",
    "withdrawal": "cash",
    "atm": "cash",
}

# Controlled item types for fees_and_limits normalization.
ITEM_TYPE_ALIASES: Dict[str, str] = {
    "fee": "fee",
    "fees": "fee",
    "charge": "fee",
    "charges": "fee",
    "limit": "limit",
    "limits": "limit",
    "threshold": "limit",
}

# Common account type cleanup.
ACCOUNT_TYPE_ALIASES: Dict[str, str] = {
    "current": "current",
    "checking": "current",
    "savings": "savings",
    "saving": "savings",
    "wallet": "wallet",
    "credit": "credit",
    "loan": "loan",
}

# Regex patterns used by helpers.
MULTISPACE_RE = re.compile(r"\s+")
NON_WORD_KEEP_BASIC_RE = re.compile(r"[^\w\s&/\-]")

##BRICK 3: Define helper functions for normalization steps, such as cleaning strings, normalizing currencies, merchants, categories, item types, account types, and deriving transaction direction.
def _is_null_like(value: object) -> bool:
    """
    Return True for values that should be treated as missing.

    Why:
    - source exports often contain None, NaN, empty strings, or whitespace-only strings
    """
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except Exception:
        pass
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _clean_str(value: object) -> Optional[str]:
    """
    Convert a value into a cleaned string or None.

    Cleaning rules:
    - strip surrounding whitespace
    - collapse repeated internal whitespace
    - keep original character casing for now

    Why:
    - foundational helper used by merchant/category/account/product normalization
    """
    if _is_null_like(value):
        return None

    text = str(value).strip()
    text = MULTISPACE_RE.sub(" ", text)

    return text or None


def _safe_upper(value: object) -> Optional[str]:
    """
    Clean a string and uppercase it.

    Why:
    - useful for currencies and compact code-like fields
    """
    text = _clean_str(value)
    if text is None:
        return None
    return text.upper()


def _normalize_currency(value: object, default_currency: Optional[str] = None) -> Optional[str]:
    """
    Normalize currency strings into canonical ISO-like codes.

    Examples:
    - 'ghc' -> 'GHS'
    - 'ghana cedi' -> 'GHS'
    - 'usd' -> 'USD'

    Why:
    - downstream spend summaries and balances depend on stable currency labels
    """
    text = _clean_str(value)

    if text is None:
        return default_currency.upper() if default_currency else None

    key = text.lower()
    if key in CURRENCY_ALIASES:
        return CURRENCY_ALIASES[key]

    # Fallback: if user already passed something like "GHS"
    if len(text) in {3, 4, 5}:
        return text.upper()

    return default_currency.upper() if default_currency else text.upper()


def _clean_merchant(value: object) -> Optional[str]:
    """
    Normalize merchant text into a cleaner display/search form.

    Cleaning rules:
    - strip whitespace
    - remove noisy punctuation while preserving simple separators (& / -)
    - collapse repeated spaces
    - title-case the result for readability

    Why:
    - recurring detection and spend grouping work better with stable merchant labels
    """
    text = _clean_str(value)
    if text is None:
        return None

    text = NON_WORD_KEEP_BASIC_RE.sub("", text)
    text = MULTISPACE_RE.sub(" ", text).strip()

    if not text:
        return None

    return text.title()


def _normalize_category(value: object) -> Optional[str]:
    """
    Normalize free-text categories into stable baseline labels.

    This is intentionally light-touch.
    Rich domain mapping belongs in category_mapping.py.
    """
    text = _clean_str(value)
    if text is None:
        return None

    key = text.lower()
    key = key.replace("&", "and")
    key = MULTISPACE_RE.sub(" ", key).strip()

    return CATEGORY_ALIASES.get(key, key)


def _normalize_item_type(value: object) -> Optional[str]:
    """
    Normalize fee/limit item types into a controlled set.

    Why:
    - status explanation and policy logic should not deal with many spelling variants
    """
    text = _clean_str(value)
    if text is None:
        return None

    key = text.lower()
    return ITEM_TYPE_ALIASES.get(key, key)


def _normalize_account_type(value: object) -> Optional[str]:
    """
    Normalize account type labels into a small stable set.
    """
    text = _clean_str(value)
    if text is None:
        return None

    key = text.lower()
    return ACCOUNT_TYPE_ALIASES.get(key, key)


def _derive_transaction_direction(amount: object) -> Optional[str]:
    """
    Infer debit/credit from the sign of the amount.

    Convention:
    - negative -> debit
    - positive -> credit
    - zero / invalid -> None

    Why:
    - useful for downstream summaries and explanation logic
    """
    if _is_null_like(amount):
        return None

    try:
        amount_value = float(amount)
    except (TypeError, ValueError):
        return None

    if amount_value < 0:
        return "debit"
    if amount_value > 0:
        return "credit"
    return None

##BRICK 4: Define main normalization functions for transactions, accounts, fees/limits, products, and metadata, applying the helper functions and normalization rules defined above.
def normalize_transactions(
    df: pd.DataFrame,
    config: NormalizationConfig,
) -> pd.DataFrame:
    """
    Normalize transactions into a stable analytical/tool-ready form.

    Outputs/behaviors:
    - normalized currency codes
    - cleaned merchant labels
    - normalized category strings
    - derived direction/date/month helper fields
    """
    out = df.copy()

    if "currency" in out.columns:
        out["currency"] = out["currency"].apply(
            lambda x: _normalize_currency(x, default_currency=config.default_currency)
        )

    if "merchant" in out.columns:
        out["merchant_clean"] = out["merchant"].apply(_clean_merchant)

    if "category" in out.columns:
        out["category"] = out["category"].apply(_normalize_category)

    if "description" in out.columns:
        out["description"] = out["description"].apply(_clean_str)

    if "transaction_id" in out.columns:
        out["transaction_id"] = out["transaction_id"].apply(_clean_str)

    if "account_id" in out.columns:
        out["account_id"] = out["account_id"].apply(_clean_str)

    if "timestamp" in out.columns:
        out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce", utc=config.timezone_utc)
        out["date"] = out["timestamp"].dt.date.astype("string")
        out["month"] = out["timestamp"].dt.to_period("M").astype("string")

    if "amount" in out.columns:
        out["amount"] = pd.to_numeric(out["amount"], errors="coerce")

    if config.derive_transaction_direction and "amount" in out.columns:
        out["direction"] = out["amount"].apply(_derive_transaction_direction)

    if config.drop_invalid_rows:
        required = ["transaction_id", "account_id", "amount", "currency", "timestamp"]
        present_required = [c for c in required if c in out.columns]
        if present_required:
            before = len(out)
            out = out.dropna(subset=present_required)
            dropped = before - len(out)
            if dropped:
                logger.info("Dropped %s invalid transaction rows during normalization", dropped)

    return out


def normalize_accounts(
    df: pd.DataFrame,
    config: NormalizationConfig,
) -> pd.DataFrame:
    """
    Normalize account records for downstream lookup and joining.
    """
    out = df.copy()

    if "account_id" in out.columns:
        out["account_id"] = out["account_id"].apply(_clean_str)

    if "account_name" in out.columns:
        out["account_name"] = out["account_name"].apply(_clean_str)

    if "account_type" in out.columns:
        out["account_type"] = out["account_type"].apply(_normalize_account_type)

    if "currency" in out.columns:
        out["currency"] = out["currency"].apply(
            lambda x: _normalize_currency(x, default_currency=config.default_currency)
        )

    if config.drop_invalid_rows:
        required = ["account_id", "account_name"]
        present_required = [c for c in required if c in out.columns]
        if present_required:
            before = len(out)
            out = out.dropna(subset=present_required)
            dropped = before - len(out)
            if dropped:
                logger.info("Dropped %s invalid account rows during normalization", dropped)

    return out


def normalize_fees_and_limits(
    df: pd.DataFrame,
    config: NormalizationConfig,
) -> pd.DataFrame:
    """
    Normalize fee/limit tables for deterministic policy lookups.
    """
    out = df.copy()

    if "item_id" in out.columns:
        out["item_id"] = out["item_id"].apply(_clean_str)

    if "item_type" in out.columns:
        out["item_type"] = out["item_type"].apply(_normalize_item_type)

    if "value" in out.columns:
        out["value"] = pd.to_numeric(out["value"], errors="coerce")

    if "unit" in out.columns:
        out["unit"] = out["unit"].apply(_safe_upper)

    if "notes" in out.columns:
        out["notes"] = out["notes"].apply(_clean_str)

    if config.drop_invalid_rows:
        required = ["item_id", "item_type", "value"]
        present_required = [c for c in required if c in out.columns]
        if present_required:
            before = len(out)
            out = out.dropna(subset=present_required)
            dropped = before - len(out)
            if dropped:
                logger.info("Dropped %s invalid fee/limit rows during normalization", dropped)

    return out


def normalize_products(
    df: pd.DataFrame,
    config: NormalizationConfig,
) -> pd.DataFrame:
    """
    Normalize product records for future product/status explanations.
    """
    out = df.copy()

    if "product_id" in out.columns:
        out["product_id"] = out["product_id"].apply(_clean_str)

    if "product_name" in out.columns:
        out["product_name"] = out["product_name"].apply(_clean_str)

    if "product_type" in out.columns:
        out["product_type"] = out["product_type"].apply(_clean_str)
        out["product_type"] = out["product_type"].str.lower()

    if config.drop_invalid_rows:
        required = ["product_id", "product_name"]
        present_required = [c for c in required if c in out.columns]
        if present_required:
            before = len(out)
            out = out.dropna(subset=present_required)
            dropped = before - len(out)
            if dropped:
                logger.info("Dropped %s invalid product rows during normalization", dropped)

    return out


def normalize_metadata(
    df: pd.DataFrame,
    config: NormalizationConfig,
) -> pd.DataFrame:
    """
    Normalize general metadata key-value rows.
    """
    out = df.copy()

    if "key" in out.columns:
        out["key"] = out["key"].apply(_clean_str)
        out["key"] = out["key"].str.lower()

    if "value" in out.columns:
        out["value"] = out["value"].apply(_clean_str)

    if "source" in out.columns:
        out["source"] = out["source"].apply(_clean_str)

    if config.drop_invalid_rows:
        required = ["key", "value"]
        present_required = [c for c in required if c in out.columns]
        if present_required:
            before = len(out)
            out = out.dropna(subset=present_required)
            dropped = before - len(out)
            if dropped:
                logger.info("Dropped %s invalid metadata rows during normalization", dropped)

    return out
##BRICK 5: Define the main normalize_bundle function that applies the specific normalization functions to each dataset in the bundle, handling errors and returning the normalized bundle.
def normalize_bundle(
    bundle: Mapping[str, pd.DataFrame],
    config: Optional[NormalizationConfig] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Normalize all datasets in a loaded bundle.

    This is the main public entrypoint for the normalization stage.

    Args:
        bundle:
            Mapping of dataset name -> ingested DataFrame
        config:
            Optional normalization configuration. If omitted, defaults are used.

    Returns:
        Dict[str, pd.DataFrame] containing normalized datasets.

    Raises:
        NormalizationError:
            If a required dataset-specific normalization step fails.
    """
    config = config or NormalizationConfig()
    normalized: Dict[str, pd.DataFrame] = {}

    try:
        if "transactions" in bundle:
            normalized["transactions"] = normalize_transactions(bundle["transactions"], config)

        if "accounts" in bundle:
            normalized["accounts"] = normalize_accounts(bundle["accounts"], config)

        if "fees_and_limits" in bundle:
            normalized["fees_and_limits"] = normalize_fees_and_limits(bundle["fees_and_limits"], config)

        if "products" in bundle:
            normalized["products"] = normalize_products(bundle["products"], config)

        if "metadata" in bundle:
            normalized["metadata"] = normalize_metadata(bundle["metadata"], config)

    except Exception as e:
        raise NormalizationError(f"Failed to normalize dataset bundle: {e}") from e

    return normalized