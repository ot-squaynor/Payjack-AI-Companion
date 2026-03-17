# app/data_pipeline/category_mapping.py
# 2026-02-26
"""Purpose: Map raw document categories (e.g., 'policy', 'help') to standardized tags for consistent retrieval and filtering."""

##BRICK 1: Header, imports, logger, exceptions, and config dataclasses
"""
Deterministic category mapping for normalized transaction data.

This module converts normalized transaction category signals into a canonical
business taxonomy that downstream recurrence logic, quality checks, and
financial tools can rely on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Mapping, Sequence

import pandas as pd


logger = logging.getLogger(__name__)


class CategoryMappingError(Exception):
    """Base exception for category mapping failures."""


class CategoryMappingInputError(CategoryMappingError):
    """Raised when the input dataframe contract is invalid."""


class CategoryMappingConfigError(CategoryMappingError):
    """Raised when mapping configuration is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class CategoryMappingRule:
    """Deterministic rule for assigning a canonical category outcome."""

    priority: int
    source_field: str
    match_type: str
    match_value: str
    target_category: str
    target_subcategory: str
    direction_constraint: str | None = None
    merchant_constraint: str | None = None


@dataclass(frozen=True, slots=True)
class CategoryMappingConfig:
    """Configuration bundle for canonical category mapping behavior."""

    allowed_categories: frozenset[str]
    allowed_subcategories: frozenset[str]
    merchant_alias_map: Mapping[str, str] = field(default_factory=dict)
    category_alias_map: Mapping[str, str] = field(default_factory=dict)
    rules: Sequence[CategoryMappingRule] = field(default_factory=tuple)
    default_category: str = "other"
    default_subcategory: str = "uncategorized"

##BRICK 2: Constants for matching logic and dataframe column names
MATCH_EXACT = "exact"
MATCH_CONTAINS = "contains"
MATCH_REGEX = "regex"

SUPPORTED_MATCH_TYPES: frozenset[str] = frozenset(
    {
        MATCH_EXACT,
        MATCH_CONTAINS,
        MATCH_REGEX,
    }
)

COL_TRANSACTION_ID = "transaction_id"
COL_AMOUNT = "amount"
COL_DIRECTION = "direction"
COL_TIMESTAMP = "timestamp"
COL_MERCHANT_NORMALIZED = "merchant_normalized"
COL_CATEGORY_NORMALIZED = "category_normalized"

REQUIRED_INPUT_COLUMNS: frozenset[str] = frozenset(
    {
        COL_TRANSACTION_ID,
        COL_AMOUNT,
        COL_DIRECTION,
        COL_TIMESTAMP,
        COL_MERCHANT_NORMALIZED,
        COL_CATEGORY_NORMALIZED,
    }
)

COL_MERCHANT_MAPPED = "merchant_mapped"
COL_CATEGORY_MAPPED = "category_mapped"
COL_SUBCATEGORY_MAPPED = "subcategory_mapped"
COL_CATEGORY_MAPPING_SOURCE = "category_mapping_source"

DEFAULT_CATEGORY = "other"
DEFAULT_SUBCATEGORY = "uncategorized"

##BRICK 3: Default configuration values for allowed categories, subcategories, alias maps, and mapping rules
DEFAULT_ALLOWED_CATEGORIES: frozenset[str] = frozenset(
    {
        "income",
        "transfer",
        "groceries",
        "transport",
        "bills",
        "shopping",
        "entertainment",
        "healthcare",
        "education",
        "savings",
        "fees",
        "cash",
        "other",
    }
)

DEFAULT_ALLOWED_SUBCATEGORIES: frozenset[str] = frozenset(
    {
        "salary",
        "peer_transfer",
        "internal_transfer",
        "supermarket",
        "fuel",
        "ride_hailing",
        "utilities",
        "mobile_money",
        "subscriptions",
        "pharmacy",
        "tuition",
        "bank_fee",
        "atm_withdrawal",
        "general",
        "uncategorized",
    }
)

DEFAULT_MERCHANT_ALIAS_MAP: dict[str, str] = {
    "melcom gh": "melcom",
    "melcom ltd": "melcom",
    "shoprite gh": "shoprite",
    "shell retail": "shell",
    "total energies": "total",
    "uber bv": "uber",
    "bolt eu": "bolt",
    "vodafone cash": "vodafone",
    "mtn momo": "mtn",
    "ecobank mobile": "ecobank",
}

DEFAULT_CATEGORY_ALIAS_MAP: dict[str, str] = {
    "supermarket": "groceries",
    "food groceries": "groceries",
    "grocery": "groceries",
    "fuel station": "transport",
    "taxi": "transport",
    "ride share": "transport",
    "utility": "bills",
    "subscription": "entertainment",
    "medical": "healthcare",
    "school": "education",
    "bank charges": "fees",
    "withdrawal": "cash",
    "unknown": DEFAULT_CATEGORY,
    "misc": DEFAULT_CATEGORY,
}

DEFAULT_CATEGORY_MAPPING_RULES: tuple[CategoryMappingRule, ...] = (
    CategoryMappingRule(
        priority=10,
        source_field=COL_DIRECTION,
        match_type=MATCH_EXACT,
        match_value="credit",
        target_category="income",
        target_subcategory="salary",
        merchant_constraint="salary",
    ),
    CategoryMappingRule(
        priority=20,
        source_field=COL_CATEGORY_NORMALIZED,
        match_type=MATCH_EXACT,
        match_value="transfer",
        target_category="transfer",
        target_subcategory="peer_transfer",
    ),
    CategoryMappingRule(
        priority=30,
        source_field=COL_MERCHANT_NORMALIZED,
        match_type=MATCH_EXACT,
        match_value="melcom",
        target_category="groceries",
        target_subcategory="supermarket",
    ),
    CategoryMappingRule(
        priority=40,
        source_field=COL_MERCHANT_NORMALIZED,
        match_type=MATCH_EXACT,
        match_value="shell",
        target_category="transport",
        target_subcategory="fuel",
    ),
    CategoryMappingRule(
        priority=50,
        source_field=COL_MERCHANT_NORMALIZED,
        match_type=MATCH_EXACT,
        match_value="uber",
        target_category="transport",
        target_subcategory="ride_hailing",
    ),
    CategoryMappingRule(
        priority=60,
        source_field=COL_CATEGORY_NORMALIZED,
        match_type=MATCH_EXACT,
        match_value="utilities",
        target_category="bills",
        target_subcategory="utilities",
    ),
    CategoryMappingRule(
        priority=70,
        source_field=COL_CATEGORY_NORMALIZED,
        match_type=MATCH_EXACT,
        match_value="bank_fee",
        target_category="fees",
        target_subcategory="bank_fee",
    ),
    CategoryMappingRule(
        priority=80,
        source_field=COL_CATEGORY_NORMALIZED,
        match_type=MATCH_EXACT,
        match_value="atm_withdrawal",
        target_category="cash",
        target_subcategory="atm_withdrawal",
    ),
)


def build_default_category_mapping_config() -> CategoryMappingConfig:
    """Build the default deterministic category mapping configuration."""
    return CategoryMappingConfig(
        allowed_categories=DEFAULT_ALLOWED_CATEGORIES,
        allowed_subcategories=DEFAULT_ALLOWED_SUBCATEGORIES,
        merchant_alias_map=DEFAULT_MERCHANT_ALIAS_MAP,
        category_alias_map=DEFAULT_CATEGORY_ALIAS_MAP,
        rules=tuple(
            sorted(
                DEFAULT_CATEGORY_MAPPING_RULES,
                key=lambda rule: rule.priority,
            )
        ),
        default_category=DEFAULT_CATEGORY,
        default_subcategory=DEFAULT_SUBCATEGORY,
    )
##BRICK 4:

##BRICK 5:

##BRICK 6:

##BRICK 7: 

##BRICK 8: 

##BRICK 9: 
