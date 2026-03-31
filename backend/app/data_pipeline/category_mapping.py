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


logger = logging.getLogger(__name__) # Logger for this module, configured by the application entry point to integrate with overall logging strategy.


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

    allowed_categories: frozenset[str] # Set of allowed canonical categories that can be assigned to transactions, used for validation and fallback logic.
    allowed_subcategories: frozenset[str] # Set of allowed canonical subcategories that can be assigned to transactions, used for validation and fallback logic.
    merchant_alias_map: Mapping[str, str] = field(default_factory=dict) # Optional mapping of normalized merchant values to standardized forms for more effective rule matching (e.g., "melcom gh" -> "melcom").
    category_alias_map: Mapping[str, str] = field(default_factory=dict) # Optional mapping of normalized category values to standardized forms for more effective rule matching (e.g., "supermarket" -> "groceries").
    rules: Sequence[CategoryMappingRule] = field(default_factory=tuple) # Ordered sequence of deterministic mapping rules, evaluated in order of priority (lowest number first) to assign canonical categories based on transaction attributes.
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

REQUIRED_INPUT_COLUMNS: frozenset[str] = frozenset( # The category mapping logic relies on these normalized columns being present in the input dataframe, as they are used for rule evaluation and alias mapping. This set is used for upfront validation to ensure the input contract is met before processing.
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

##BRICK 4: Validation functions for category mapping configuration and input dataframe contract
def validate_category_mapping_config(config: CategoryMappingConfig) -> None:
    """Validate that the category mapping configuration is internally consistent."""
    if not config.allowed_categories:
        raise CategoryMappingConfigError("allowed_categories must not be empty.")

    if not config.allowed_subcategories:
        raise CategoryMappingConfigError("allowed_subcategories must not be empty.")

    if config.default_category not in config.allowed_categories:
        raise CategoryMappingConfigError(
            f"default_category '{config.default_category}' is not in allowed_categories."
        )

    if config.default_subcategory not in config.allowed_subcategories:
        raise CategoryMappingConfigError(
            (
                f"default_subcategory '{config.default_subcategory}' "
                "is not in allowed_subcategories."
            )
        )

    seen_priorities: set[int] = set()

    for rule in config.rules:
        if rule.priority in seen_priorities:
            raise CategoryMappingConfigError(
                f"Duplicate rule priority detected: {rule.priority}."
            )
        seen_priorities.add(rule.priority)

        if rule.match_type not in SUPPORTED_MATCH_TYPES:
            raise CategoryMappingConfigError(
                f"Unsupported match_type '{rule.match_type}' in rule priority {rule.priority}."
            )

        if rule.source_field not in REQUIRED_INPUT_COLUMNS:
            raise CategoryMappingConfigError(
                (
                    f"Unsupported source_field '{rule.source_field}' in "
                    f"rule priority {rule.priority}."
                )
            )

        if rule.target_category not in config.allowed_categories:
            raise CategoryMappingConfigError(
                (
                    f"target_category '{rule.target_category}' in "
                    f"rule priority {rule.priority} is not allowed."
                )
            )

        if rule.target_subcategory not in config.allowed_subcategories:
            raise CategoryMappingConfigError(
                (
                    f"target_subcategory '{rule.target_subcategory}' in "
                    f"rule priority {rule.priority} is not allowed."
                )
            )

        if not rule.match_value.strip():
            raise CategoryMappingConfigError(
                f"Empty match_value in rule priority {rule.priority}."
            )


def validate_category_mapping_inputs(df: pd.DataFrame) -> None:
    """Validate that the normalized dataframe contains the required mapping columns."""
    missing_columns = REQUIRED_INPUT_COLUMNS.difference(df.columns)

    if missing_columns:
        missing_sorted = ", ".join(sorted(missing_columns))
        raise CategoryMappingInputError(
            f"Input dataframe is missing required columns: {missing_sorted}."
        )

    if df.empty:
        logger.warning("Category mapping received an empty dataframe.")

##BRICK 5: Core logic for normalizing candidate values and evaluating whether a transaction row matches a given mapping rule
def normalize_mapping_value(value: object) -> str:
    """Normalize a candidate scalar value for deterministic rule matching."""
    if value is None:
        return ""

    if pd.isna(value):
        return ""

    normalized = str(value).strip().lower()
    return normalized


def _matches_value(match_type: str, candidate_value: str, match_value: str) -> bool:
    """Return True when a candidate value satisfies the configured match rule."""
    if match_type == MATCH_EXACT:
        return candidate_value == match_value

    if match_type == MATCH_CONTAINS:
        return match_value in candidate_value

    if match_type == MATCH_REGEX:
        return re.search(match_value, candidate_value) is not None

    raise CategoryMappingConfigError(f"Unsupported match_type: {match_type}.")


def _matches_optional_constraint(
    candidate_value: str,
    constraint_value: str | None,
) -> bool:
    """Return True when an optional normalized constraint is satisfied."""
    if constraint_value is None:
        return True

    return candidate_value == normalize_mapping_value(constraint_value)


def matches_rule(
    *,
    rule: CategoryMappingRule,
    source_value: object,
    direction_value: object,
    merchant_value: object,
) -> bool:
    """Evaluate whether a deterministic mapping rule applies to a transaction row."""
    candidate_source = normalize_mapping_value(source_value)
    candidate_direction = normalize_mapping_value(direction_value)
    candidate_merchant = normalize_mapping_value(merchant_value)
    normalized_match_value = normalize_mapping_value(rule.match_value)

    if not _matches_value(rule.match_type, candidate_source, normalized_match_value):
        return False

    if not _matches_optional_constraint(
        candidate_direction,
        rule.direction_constraint,
    ):
        return False

    if not _matches_optional_constraint(
        candidate_merchant,
        rule.merchant_constraint,
    ):
        return False

    return True

##BRICK 6: Logic to apply merchant and category alias maps to the normalized dataframe before rule evaluation
def apply_alias_maps(
    df: pd.DataFrame,
    config: CategoryMappingConfig,
) -> pd.DataFrame:
    """Apply deterministic merchant and category alias standardization."""
    mapped_df = df.copy()

    mapped_df[COL_MERCHANT_MAPPED] = (
        mapped_df[COL_MERCHANT_NORMALIZED]
        .map(
            lambda value: config.merchant_alias_map.get(
                normalize_mapping_value(value),
                normalize_mapping_value(value),
            )
        )
    )

    mapped_df[COL_CATEGORY_MAPPED] = (
        mapped_df[COL_CATEGORY_NORMALIZED]
        .map(
            lambda value: config.category_alias_map.get(
                normalize_mapping_value(value),
                normalize_mapping_value(value),
            )
        )
    )

    return mapped_df
##BRICK 7: Logic to resolve canonical categories for transaction rows
def resolve_category_for_row(
    *,
    merchant_mapped: object,
    category_mapped: object,
    direction_value: object,
    config: CategoryMappingConfig,
) -> tuple[str, str, str]:
    """Resolve canonical category outputs for a single transaction row."""
    normalized_merchant = normalize_mapping_value(merchant_mapped)
    normalized_category = normalize_mapping_value(category_mapped)
    normalized_direction = normalize_mapping_value(direction_value)

    for rule in config.rules:
        if rule.source_field == COL_MERCHANT_NORMALIZED:
            source_value = normalized_merchant
        elif rule.source_field == COL_CATEGORY_NORMALIZED:
            source_value = normalized_category
        elif rule.source_field == COL_DIRECTION:
            source_value = normalized_direction
        else:
            raise CategoryMappingConfigError(
                f"Unsupported source_field in rule priority {rule.priority}: {rule.source_field}."
            )

        if matches_rule(
            rule=rule,
            source_value=source_value,
            direction_value=normalized_direction,
            merchant_value=normalized_merchant,
        ):
            return (
                rule.target_category,
                rule.target_subcategory,
                f"rule:{rule.priority}",
            )

    if normalized_category in config.allowed_categories:
        return normalized_category, "general", "category_alias"

    return (
        config.default_category,
        config.default_subcategory,
        "default_fallback",
    )

##BRICK 8: 
def map_categories(
    df: pd.DataFrame,
    config: CategoryMappingConfig | None = None,
) -> pd.DataFrame:
    """Map normalized transaction data into the canonical business taxonomy."""
    resolved_config = config or build_default_category_mapping_config()

    validate_category_mapping_config(resolved_config)
    validate_category_mapping_inputs(df)

    mapped_df = apply_alias_maps(df=df, config=resolved_config).copy()

    resolutions = mapped_df.apply(
        lambda row: resolve_category_for_row(
            merchant_mapped=row[COL_MERCHANT_MAPPED],
            category_mapped=row[COL_CATEGORY_MAPPED],
            direction_value=row[COL_DIRECTION],
            config=resolved_config,
        ),
        axis=1,
        result_type="expand",
    )

    resolutions.columns = [
        COL_CATEGORY_MAPPED,
        COL_SUBCATEGORY_MAPPED,
        COL_CATEGORY_MAPPING_SOURCE,
    ]

    mapped_df[COL_CATEGORY_MAPPED] = resolutions[COL_CATEGORY_MAPPED]
    mapped_df[COL_SUBCATEGORY_MAPPED] = resolutions[COL_SUBCATEGORY_MAPPED]
    mapped_df[COL_CATEGORY_MAPPING_SOURCE] = resolutions[COL_CATEGORY_MAPPING_SOURCE]

    return mapped_df

##BRICK 9: Function to summarize category mapping coverage
def mapping_coverage_summary(df: pd.DataFrame) -> dict[str, int]:
    """Summarize category mapping coverage and fallback usage."""
    if COL_CATEGORY_MAPPING_SOURCE not in df.columns:
        raise CategoryMappingInputError(
            f"Missing required column for coverage summary: {COL_CATEGORY_MAPPING_SOURCE}."
        )

    source_counts = (
        df[COL_CATEGORY_MAPPING_SOURCE]
        .fillna("missing")
        .astype(str)
        .value_counts(dropna=False)
        .to_dict()
    )

    summary = {
        "total_rows": int(len(df)),
        "default_fallback_rows": int(source_counts.get("default_fallback", 0)),
        "category_alias_rows": int(source_counts.get("category_alias", 0)),
        "rule_mapped_rows": int(
            sum(
                count
                for source, count in source_counts.items()
                if source.startswith("rule:")
            )
        ),
    }

    for source, count in source_counts.items():
        summary[f"source::{source}"] = int(count)
    return summary
##