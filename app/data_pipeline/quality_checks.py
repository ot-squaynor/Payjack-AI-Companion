# app/data_pipeline/quality_checks.py
# 2026-02-25
"""Purpose: Gatekeeping (schema validation, missing fields, drift detection, doc quality, duplicate chunks).
This is a big win for fintech: it prevents bad KB content from poisoning retrieval."""

##BRICK 1:
"""
Deterministic quality checks for processed transaction data.

This module validates the final processed dataframe after normalization,
category mapping, and recurrence detection, producing structured and
auditable quality-check findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Sequence


logger = logging.getLogger(__name__)


class QualityCheckError(Exception):
    """Base exception for quality check failures."""


class QualityCheckInputError(QualityCheckError):
    """Raised when the dataframe cannot be validated due to missing structure."""


SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"


@dataclass(frozen=True, slots=True)
class QualityCheckFinding:
    """Represents a single quality check finding."""

    check_name: str
    severity: str
    message: str
    row_count: int
    sample_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class QualityCheckReport:
    """Represents the full quality check report."""

    passed: bool
    finding_count: int
    error_count: int
    warning_count: int
    info_count: int
    findings: tuple[QualityCheckFinding, ...]


@dataclass(frozen=True, slots=True)
class QualityCheckConfig:
    """Configuration for deterministic quality checks."""

    max_sample_ids_per_finding: int = 5
    allowed_directions: frozenset[str] = frozenset({"credit", "debit"})
    allowed_categories: frozenset[str] = frozenset()
    allowed_subcategories: frozenset[str] = frozenset()
    allowed_cadences: frozenset[str] = frozenset()
    allowed_confidence_levels: frozenset[str] = frozenset()
    min_timestamp: str = "2000-01-01"
    allow_future_timestamps: bool = False

##BRICK 2: Check Implementations
import pandas as pd


CHECK_REQUIRED_COLUMNS = "check_required_columns"
CHECK_DUPLICATE_TRANSACTION_IDS = "check_duplicate_transaction_ids"
CHECK_NULL_CRITICAL_FIELDS = "check_null_critical_fields"
CHECK_INVALID_DIRECTIONS = "check_invalid_directions"
CHECK_INVALID_CATEGORIES = "check_invalid_categories"
CHECK_INVALID_SUBCATEGORIES = "check_invalid_subcategories"
CHECK_INVALID_RECURRENCE_CADENCE = "check_invalid_recurrence_cadence"
CHECK_INVALID_RECURRENCE_CONFIDENCE = "check_invalid_recurrence_confidence"
CHECK_IMPOSSIBLE_TIMESTAMPS = "check_impossible_timestamps"
CHECK_IMPOSSIBLE_AMOUNTS = "check_impossible_amounts"
CHECK_RECURRING_FIELD_CONSISTENCY = "check_recurring_field_consistency"


COL_TRANSACTION_ID = "transaction_id"
COL_TIMESTAMP = "timestamp"
COL_AMOUNT = "amount"
COL_DIRECTION = "direction"
COL_MERCHANT_MAPPED = "merchant_mapped"
COL_CATEGORY_MAPPED = "category_mapped"
COL_SUBCATEGORY_MAPPED = "subcategory_mapped"
COL_CATEGORY_MAPPING_SOURCE = "category_mapping_source"

COL_IS_RECURRING = "is_recurring"
COL_RECURRING_CADENCE = "recurrence_cadence"
COL_RECURRING_CONFIDENCE = "recurrence_confidence"
COL_RECURRING_GROUP_KEY = "recurrence_group_key"
COL_RECURRING_OCCURRENCE_COUNT = "recurrence_occurrence_count"


REQUIRED_PROCESSED_COLUMNS: frozenset[str] = frozenset(
    {
        COL_TRANSACTION_ID,
        COL_TIMESTAMP,
        COL_AMOUNT,
        COL_DIRECTION,
        COL_MERCHANT_MAPPED,
        COL_CATEGORY_MAPPED,
        COL_SUBCATEGORY_MAPPED,
        COL_CATEGORY_MAPPING_SOURCE,
        COL_IS_RECURRING,
        COL_RECURRING_CADENCE,
        COL_RECURRING_CONFIDENCE,
        COL_RECURRING_GROUP_KEY,
        COL_RECURRING_OCCURRENCE_COUNT,
    }
)
##BRICK 3: Default Configuration Values
DEFAULT_MAX_SAMPLE_IDS_PER_FINDING = 5
DEFAULT_MIN_TIMESTAMP = "2000-01-01"
DEFAULT_ALLOW_FUTURE_TIMESTAMPS = False

DEFAULT_ALLOWED_DIRECTIONS: frozenset[str] = frozenset({"credit", "debit"})

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

DEFAULT_ALLOWED_CADENCES: frozenset[str] = frozenset(
    {
        "none",
        "weekly",
        "biweekly",
        "monthly",
        "irregular",
    }
)

DEFAULT_ALLOWED_CONFIDENCE_LEVELS: frozenset[str] = frozenset(
    {
        "low",
        "medium",
        "high",
    }
)


def build_default_quality_check_config() -> QualityCheckConfig:
    """Build the default deterministic quality-check configuration."""
    return QualityCheckConfig(
        max_sample_ids_per_finding=DEFAULT_MAX_SAMPLE_IDS_PER_FINDING,
        allowed_directions=DEFAULT_ALLOWED_DIRECTIONS,
        allowed_categories=DEFAULT_ALLOWED_CATEGORIES,
        allowed_subcategories=DEFAULT_ALLOWED_SUBCATEGORIES,
        allowed_cadences=DEFAULT_ALLOWED_CADENCES,
        allowed_confidence_levels=DEFAULT_ALLOWED_CONFIDENCE_LEVELS,
        min_timestamp=DEFAULT_MIN_TIMESTAMP,
        allow_future_timestamps=DEFAULT_ALLOW_FUTURE_TIMESTAMPS,
    )
##BRICK 4: Input Validation and Finding Construction
def validate_quality_check_inputs(df: pd.DataFrame) -> None:
    """Validate that the dataframe contains all required processed columns."""
    missing_columns = REQUIRED_PROCESSED_COLUMNS.difference(df.columns)

    if missing_columns:
        missing_sorted = ", ".join(sorted(missing_columns))
        raise QualityCheckInputError(
            f"Input dataframe is missing required columns: {missing_sorted}."
        )

    if df.empty:
        logger.warning("Quality checks received an empty dataframe.")


def _truncate_sample_ids(
    ids: Sequence[object],
    max_items: int,
) -> tuple[str, ...]:
    """Return a truncated tuple of stringified sample IDs."""
    return tuple(str(i) for i in list(ids)[:max_items])


def make_finding(
    *,
    check_name: str,
    severity: str,
    message: str,
    row_ids: Sequence[object],
    config: QualityCheckConfig,
) -> QualityCheckFinding:
    """Construct a standardized QualityCheckFinding."""
    return QualityCheckFinding(
        check_name=check_name,
        severity=severity,
        message=message,
        row_count=len(row_ids),
        sample_ids=_truncate_sample_ids(
            row_ids,
            config.max_sample_ids_per_finding,
        ),
    )
##BRICK :

##BRICK :