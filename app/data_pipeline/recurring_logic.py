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
from typing import Final, Sequence
from app.data_pipeline.category_mapping import normalize_mapping_value


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
##BRICK 4: Configuration and Input Validation
def validate_recurring_detection_config(config: RecurringDetectionConfig) -> None:
    """Validate that the recurrence detection configuration is internally consistent."""
    if config.min_group_size < 2:
        raise RecurringLogicConfigError("min_group_size must be at least 2.")

    if config.amount_tolerance_ratio < 0:
        raise RecurringLogicConfigError(
            "amount_tolerance_ratio must be greater than or equal to 0."
        )

    if config.amount_tolerance_absolute < 0:
        raise RecurringLogicConfigError(
            "amount_tolerance_absolute must be greater than or equal to 0."
        )

    if config.weekly_window_days < 0:
        raise RecurringLogicConfigError(
            "weekly_window_days must be greater than or equal to 0."
        )

    if config.biweekly_window_days < 0:
        raise RecurringLogicConfigError(
            "biweekly_window_days must be greater than or equal to 0."
        )

    if config.monthly_window_days < 0:
        raise RecurringLogicConfigError(
            "monthly_window_days must be greater than or equal to 0."
        )

    if config.medium_confidence_min_occurrences < config.min_group_size:
        raise RecurringLogicConfigError(
            "medium_confidence_min_occurrences must be greater than or equal to min_group_size."
        )

    if config.high_confidence_min_occurrences < config.medium_confidence_min_occurrences:
        raise RecurringLogicConfigError(
            "high_confidence_min_occurrences must be greater than or equal to "
            "medium_confidence_min_occurrences."
        )

    if config.irregular_max_interval_span_days < 0:
        raise RecurringLogicConfigError(
            "irregular_max_interval_span_days must be greater than or equal to 0."
        )


def validate_recurring_logic_inputs(df: pd.DataFrame) -> None:
    """Validate that the mapped dataframe contains the required recurrence columns."""
    missing_columns = REQUIRED_INPUT_COLUMNS.difference(df.columns)

    if missing_columns:
        missing_sorted = ", ".join(sorted(missing_columns))
        raise RecurringLogicInputError(
            f"Input dataframe is missing required columns: {missing_sorted}."
        )

    if df.empty:
        logger.warning("Recurring detection received an empty dataframe.")


def coerce_recurring_logic_types(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce timestamp and amount columns into deterministic processing types."""
    coerced_df = df.copy()

    coerced_df[COL_TIMESTAMP] = pd.to_datetime(
        coerced_df[COL_TIMESTAMP],
        errors="coerce",
        utc=True,
    )
    coerced_df[COL_AMOUNT] = pd.to_numeric(
        coerced_df[COL_AMOUNT],
        errors="coerce",
    )

    invalid_timestamp_count = int(coerced_df[COL_TIMESTAMP].isna().sum())
    invalid_amount_count = int(coerced_df[COL_AMOUNT].isna().sum())

    if invalid_timestamp_count > 0:
        raise RecurringLogicInputError(
            f"{invalid_timestamp_count} rows have invalid timestamps after coercion."
        )

    if invalid_amount_count > 0:
        raise RecurringLogicInputError(
            f"{invalid_amount_count} rows have invalid amounts after coercion."
        )

    return coerced_df

##BRICK 5: Recurrence Grouping and Stability Checks
def build_recurrence_group_key(
    merchant_mapped: object,
    category_mapped: object,
    subcategory_mapped: object,
    direction_value: object,
) -> str:
    """Build a deterministic recurrence grouping key from stable transaction attributes."""
    merchant = normalize_mapping_value(merchant_mapped)
    category = normalize_mapping_value(category_mapped)
    subcategory = normalize_mapping_value(subcategory_mapped)
    direction = normalize_mapping_value(direction_value)

    return f"{merchant}|{category}|{subcategory}|{direction}"


def amounts_within_tolerance(
    values: Sequence[float],
    config: RecurringDetectionConfig,
) -> bool:
    """Check whether a sequence of amounts is stable within configured tolerance."""
    if not values:
        return False

    reference = float(values[0])

    for value in values:
        absolute_diff = abs(value - reference)
        ratio_diff = absolute_diff / reference if reference != 0 else absolute_diff

        if (
            absolute_diff > config.amount_tolerance_absolute
            and ratio_diff > config.amount_tolerance_ratio
        ):
            return False

    return True


def compute_sorted_intervals(
    timestamps: Sequence[pd.Timestamp],
) -> list[int]:
    """Compute sorted day intervals between consecutive timestamps."""
    if len(timestamps) < 2:
        return []

    sorted_ts = sorted(timestamps)
    intervals: list[int] = []

    for i in range(1, len(sorted_ts)):
        delta = sorted_ts[i] - sorted_ts[i - 1]
        intervals.append(int(delta.days))

    return intervals

##BRICK 6: 
def normalize_recurring_value(value: object) -> str:
    """Normalize a scalar value for deterministic recurrence comparisons."""
    if value is None:
        return ""

    if pd.isna(value):
        return ""

    return str(value).strip().lower()


def _all_intervals_within_window(
    intervals: Sequence[int],
    target_days: int,
    window_days: int,
) -> bool:
    """Return True when all intervals fall within the configured cadence window."""
    if not intervals:
        return False

    return all(abs(interval - target_days) <= window_days for interval in intervals)


def infer_recurrence_cadence(
    intervals: Sequence[int],
    config: RecurringDetectionConfig,
) -> str:
    """Infer recurrence cadence from sorted transaction intervals."""
    if not intervals:
        return CADENCE_NONE

    if _all_intervals_within_window(intervals, 7, config.weekly_window_days):
        return CADENCE_WEEKLY

    if _all_intervals_within_window(intervals, 14, config.biweekly_window_days):
        return CADENCE_BIWEEKLY

    if _all_intervals_within_window(intervals, 30, config.monthly_window_days):
        return CADENCE_MONTHLY

    interval_span = max(intervals) - min(intervals)
    if interval_span <= config.irregular_max_interval_span_days:
        return CADENCE_IRREGULAR

    return CADENCE_NONE


def infer_recurrence_confidence(
    *,
    occurrence_count: int,
    cadence: str,
    amount_stable: bool,
    intervals: Sequence[int],
    config: RecurringDetectionConfig,
) -> str:
    """Infer deterministic recurrence confidence from group characteristics."""
    if cadence == CADENCE_NONE or occurrence_count < config.min_group_size:
        return CONFIDENCE_LOW

    if not amount_stable:
        return CONFIDENCE_LOW

    if not intervals:
        return CONFIDENCE_LOW

    interval_span = max(intervals) - min(intervals)

    if (
        occurrence_count >= config.high_confidence_min_occurrences
        and cadence in {CADENCE_WEEKLY, CADENCE_BIWEEKLY, CADENCE_MONTHLY}
        and interval_span <= min(
            config.weekly_window_days,
            config.biweekly_window_days,
            config.monthly_window_days,
        )
    ):
        return CONFIDENCE_HIGH

    if occurrence_count >= config.medium_confidence_min_occurrences:
        return CONFIDENCE_MEDIUM

    return CONFIDENCE_LOW

##BRICK 7: Main Recurrence Assessment Function
def assess_group_recurrence(
    group_df: pd.DataFrame,
    config: RecurringDetectionConfig,
) -> dict[str, object]:
    """Assess recurrence characteristics for a grouped set of transactions."""
    occurrence_count = int(len(group_df))

    timestamps = group_df[COL_TIMESTAMP].tolist()
    amounts = group_df[COL_AMOUNT].tolist()

    intervals = compute_sorted_intervals(timestamps)
    amount_stable = amounts_within_tolerance(amounts, config)

    cadence = infer_recurrence_cadence(intervals, config)

    confidence = infer_recurrence_confidence(
        occurrence_count=occurrence_count,
        cadence=cadence,
        amount_stable=amount_stable,
        intervals=intervals,
        config=config,
    )

    is_recurring = (
        occurrence_count >= config.min_group_size
        and cadence != CADENCE_NONE
        and amount_stable
    )

    reference_amount = float(amounts[0]) if amounts else 0.0
    avg_interval = float(sum(intervals) / len(intervals)) if intervals else 0.0

    return {
        COL_IS_RECURRING: bool(is_recurring),
        COL_RECURRING_CADENCE: cadence,
        COL_RECURRING_CONFIDENCE: confidence,
        COL_RECURRING_OCCURRENCE_COUNT: occurrence_count,
        COL_RECURRING_INTERVAL_DAYS: avg_interval,
        COL_RECURRING_AMOUNT_REFERENCE: reference_amount,
    }

##BRICK 8: Main Detection Function
def detect_recurring_transactions(
    df: pd.DataFrame,
    config: RecurringDetectionConfig | None = None,
) -> pd.DataFrame:
    """Detect and annotate recurring transactions in a dataframe."""
    resolved_config = config or build_default_recurring_detection_config()

    validate_recurring_detection_config(resolved_config)
    validate_recurring_logic_inputs(df)

    working_df = coerce_recurring_logic_types(df)

    working_df[COL_RECURRING_GROUP_KEY] = working_df.apply(
        lambda row: build_recurrence_group_key(
            merchant_mapped=row[COL_MERCHANT_MAPPED],
            category_mapped=row[COL_CATEGORY_MAPPED],
            subcategory_mapped=row[COL_SUBCATEGORY_MAPPED],
            direction_value=row[COL_DIRECTION],
        ),
        axis=1,
    )

    results = []

    for group_key, group_df in working_df.groupby(COL_RECURRING_GROUP_KEY):
        assessment = assess_group_recurrence(group_df, resolved_config)

        for idx in group_df.index:
            row_result = {
                COL_RECURRING_GROUP_KEY: group_key,
                **assessment,
            }
            results.append((idx, row_result))

    result_df = pd.DataFrame(
        [item[1] for item in results],
        index=[item[0] for item in results],
    )

    for col in result_df.columns:
        working_df[col] = result_df[col]

    return working_df
##BRICK 9: