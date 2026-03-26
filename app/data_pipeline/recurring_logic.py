# app/data_pipeline/recurring_logic.py
# 2026-02-25
"""Potentially redundant with tools

Purpose: Logic for recurring detection.
Concern: You also have app/tools/recurring_detection.py. That’s a duplication smell.

If data_pipeline/recurring_logic.py is for offline labeling (precomputing recurring flags), keep it.

If it’s the same logic as the runtime tool, consolidate into one shared module (e.g., app/domain/recurring.py) and import from both places."""

##BRICK 1: Deterministic Recurring Transaction Detection
"""
Deterministic recurring transaction detection for mapped transaction data.

This module analyzes processed transaction records and assigns recurrence
signals such as cadence, confidence, and grouping metadata for downstream
financial tools and quality checks.
"""
#Import statements
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Final


logger = logging.getLogger(__name__)


class RecurringLogicError(Exception):
    """Base exception for recurring transaction detection failures."""


class RecurringLogicInputError(RecurringLogicError):
    """Raised when the input dataframe contract is invalid."""


class RecurringLogicConfigError(RecurringLogicError):
    """Raised when recurrence configuration is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class RecurringDetectionConfig:
    """Configuration thresholds for deterministic recurring transaction detection."""

    min_group_size: int = 3
    amount_tolerance_ratio: float = 0.05
    amount_tolerance_absolute: float = 5.0
    weekly_window_days: int = 2
    biweekly_window_days: int = 3
    monthly_window_days: int = 5
    high_confidence_min_occurrences: int = 4
    medium_confidence_min_occurrences: int = 3
    irregular_max_interval_span_days: int = 10

# Default values for the recurring detection configuration
DEFAULT_MIN_GROUP_SIZE: Final[int] = 3
DEFAULT_AMOUNT_TOLERANCE_RATIO: Final[float] = 0.05
DEFAULT_AMOUNT_TOLERANCE_ABSOLUTE: Final[float] = 5.0
DEFAULT_WEEKLY_WINDOW_DAYS: Final[int] = 2
DEFAULT_BIWEEKLY_WINDOW_DAYS: Final[int] = 3
DEFAULT_MONTHLY_WINDOW_DAYS: Final[int] = 5
DEFAULT_HIGH_CONFIDENCE_MIN_OCCURRENCES: Final[int] = 4
DEFAULT_MEDIUM_CONFIDENCE_MIN_OCCURRENCES: Final[int] = 3
DEFAULT_IRREGULAR_MAX_INTERVAL_SPAN_DAYS: Final[int] = 10

##BRICK 2: Constants and Column Definitions
#from typing import Final
import pandas as pd


COL_TRANSACTION_ID = "transaction_id"
COL_TIMESTAMP = "timestamp"
COL_AMOUNT = "amount"
COL_DIRECTION = "direction"
COL_MERCHANT_MAPPED = "merchant_mapped"
COL_CATEGORY_MAPPED = "category_mapped"
COL_SUBCATEGORY_MAPPED = "subcategory_mapped"

REQUIRED_INPUT_COLUMNS: frozenset[str] = frozenset(
    {
        COL_TRANSACTION_ID,
        COL_TIMESTAMP,
        COL_AMOUNT,
        COL_DIRECTION,
        COL_MERCHANT_MAPPED,
        COL_CATEGORY_MAPPED,
        COL_SUBCATEGORY_MAPPED,
    }
)

COL_IS_RECURRING = "is_recurring"
COL_RECURRING_CADENCE = "recurrence_cadence"
COL_RECURRING_CONFIDENCE = "recurrence_confidence"
COL_RECURRING_GROUP_KEY = "recurrence_group_key"
COL_RECURRING_OCCURRENCE_COUNT = "recurrence_occurrence_count"
COL_RECURRING_INTERVAL_DAYS = "recurrence_interval_days"
COL_RECURRING_AMOUNT_REFERENCE = "recurrence_amount_reference"

CADENCE_NONE = "none"
CADENCE_WEEKLY = "weekly"
CADENCE_BIWEEKLY = "biweekly"
CADENCE_MONTHLY = "monthly"
CADENCE_IRREGULAR = "irregular"

ALLOWED_CADENCES: frozenset[str] = frozenset(
    {
        CADENCE_NONE,
        CADENCE_WEEKLY,
        CADENCE_BIWEEKLY,
        CADENCE_MONTHLY,
        CADENCE_IRREGULAR,
    }
)

CONFIDENCE_LOW = "low"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_HIGH = "high"

ALLOWED_CONFIDENCE_LEVELS: frozenset[str] = frozenset(
    {
        CONFIDENCE_LOW,
        CONFIDENCE_MEDIUM,
        CONFIDENCE_HIGH,
    }
)

##BRICK 3: Default Configuration Builder
def build_default_recurring_detection_config() -> RecurringDetectionConfig:
    """Build the default deterministic recurrence detection configuration."""
    return RecurringDetectionConfig(
        min_group_size=DEFAULT_MIN_GROUP_SIZE,
        amount_tolerance_ratio=DEFAULT_AMOUNT_TOLERANCE_RATIO,
        amount_tolerance_absolute=DEFAULT_AMOUNT_TOLERANCE_ABSOLUTE,
        weekly_window_days=DEFAULT_WEEKLY_WINDOW_DAYS,
        biweekly_window_days=DEFAULT_BIWEEKLY_WINDOW_DAYS,
        monthly_window_days=DEFAULT_MONTHLY_WINDOW_DAYS,
        high_confidence_min_occurrences=DEFAULT_HIGH_CONFIDENCE_MIN_OCCURRENCES,
        medium_confidence_min_occurrences=DEFAULT_MEDIUM_CONFIDENCE_MIN_OCCURRENCES,
        irregular_max_interval_span_days=DEFAULT_IRREGULAR_MAX_INTERVAL_SPAN_DAYS,
    )
##BRICK :
##BRICK :