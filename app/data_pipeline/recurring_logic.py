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
##BRICK :