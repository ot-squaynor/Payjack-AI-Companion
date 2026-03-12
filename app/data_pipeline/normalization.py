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

##BRICK 4: