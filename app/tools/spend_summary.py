# app/tools/spend_summary.py
# 2026-02-25
"""Purpose: Deterministic aggregation (category totals, merchants, trends).
Critical rule: LLM must not change these outputs."""
##BRICK 1: Context and imports
"""
Deterministic spend summary tool for structured transaction data.

This module computes read-only spend aggregates from already-processed
transaction datasets. It does not perform I/O, LLM calls, RAG retrieval,
or any mutation of the input dataframe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

import logging

import pandas as pd

logger = logging.getLogger(__name__)

DEBIT = "debit"
CREDIT = "credit"

DEFAULT_DIRECTION: str = DEBIT
DEFAULT_GROUP_LIMIT: int = 10
DEFAULT_SORT_DESCENDING: bool = True

ALLOWED_DIRECTIONS: frozenset[str] = frozenset({DEBIT, CREDIT})

ALLOWED_GROUP_BY: frozenset[str] = frozenset(
    {
        "category",
        "subcategory",
        "merchant",
        "account",
        "currency",
        "month",
    }
)

REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        "transaction_id",
        "account_id",
        "timestamp",
        "amount",
        "currency",
        "direction",
        "category",
        "subcategory",
        "merchant",
    }
)


class SpendSummaryError(Exception):
    """Base exception for spend summary tool failures."""


class SpendSummaryInputError(SpendSummaryError):
    """Raised when spend summary inputs are invalid."""


@dataclass(frozen=True, slots=True)
class SpendSummaryRequest:
    """Deterministic request contract for spend summary queries."""

    user_id: str | None = None
    account_ids: tuple[str, ...] = ()
    start_date: str | None = None
    end_date: str | None = None
    categories: tuple[str, ...] = ()
    merchants: tuple[str, ...] = ()
    direction: Literal["debit", "credit"] = DEFAULT_DIRECTION
    group_by: Literal[
        "category",
        "subcategory",
        "merchant",
        "account",
        "currency",
        "month",
    ] | None = None
    limit: int = DEFAULT_GROUP_LIMIT


@dataclass(frozen=True, slots=True)
class GroupedSpendRow:
    """Single grouped spend summary row."""

    key: str
    total_amount: Decimal
    transaction_count: int
    currency: str | None = None


@dataclass(frozen=True, slots=True)
class SpendSummaryResult:
    """Structured spend summary output for downstream orchestration."""

    total_amount: Decimal
    transaction_count: int
    currency_breakdown: dict[str, Decimal]
    grouped_breakdown: tuple[GroupedSpendRow, ...] = ()
    applied_filters: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

##BRICK 2: Normalization and validation functions
def _normalize_string_tuple(values: Any) -> tuple[str, ...]:
    """Normalize string-like filter inputs into a clean tuple of strings."""
    if values is None:
        return ()

    if isinstance(values, str):
        candidate_values = [values]
    elif isinstance(values, (list, tuple, set, frozenset)):
        candidate_values = list(values)
    else:
        raise SpendSummaryInputError("Filter values must be a string, sequence, or None.")

    normalized: list[str] = []
    for value in candidate_values:
        if value is None:
            continue
        if not isinstance(value, str):
            raise SpendSummaryInputError("All filter values must be strings.")
        cleaned = value.strip()
        if cleaned:
            normalized.append(cleaned)

    return tuple(normalized)


def normalize_spend_summary_request(
    *,
    user_id: str | None = None,
    account_ids: Any = None,
    start_date: str | None = None,
    end_date: str | None = None,
    categories: Any = None,
    merchants: Any = None,
    direction: str = DEFAULT_DIRECTION,
    group_by: str | None = None,
    limit: int = DEFAULT_GROUP_LIMIT,
) -> SpendSummaryRequest:
    """Validate and normalize raw request values into a deterministic request contract."""
    cleaned_user_id = user_id.strip() if isinstance(user_id, str) and user_id.strip() else None
    cleaned_start_date = start_date.strip() if isinstance(start_date, str) and start_date.strip() else None
    cleaned_end_date = end_date.strip() if isinstance(end_date, str) and end_date.strip() else None

    normalized_direction = direction.strip().lower() if isinstance(direction, str) and direction.strip() else DEFAULT_DIRECTION
    if normalized_direction not in ALLOWED_DIRECTIONS:
        raise SpendSummaryInputError(
            f"Unsupported direction '{direction}'. Allowed values: {sorted(ALLOWED_DIRECTIONS)}."
        )

    normalized_group_by: str | None = None
    if group_by is not None:
        if not isinstance(group_by, str) or not group_by.strip():
            raise SpendSummaryInputError("group_by must be a non-empty string when provided.")
        normalized_group_by = group_by.strip().lower()
        if normalized_group_by not in ALLOWED_GROUP_BY:
            raise SpendSummaryInputError(
                f"Unsupported group_by '{group_by}'. Allowed values: {sorted(ALLOWED_GROUP_BY)}."
            )

    if not isinstance(limit, int):
        raise SpendSummaryInputError("limit must be an integer.")
    if limit <= 0:
        raise SpendSummaryInputError("limit must be greater than zero.")

    if cleaned_start_date and cleaned_end_date and cleaned_start_date > cleaned_end_date:
        raise SpendSummaryInputError("start_date must be less than or equal to end_date.")

    return SpendSummaryRequest(
        user_id=cleaned_user_id,
        account_ids=_normalize_string_tuple(account_ids),
        start_date=cleaned_start_date,
        end_date=cleaned_end_date,
        categories=_normalize_string_tuple(categories),
        merchants=_normalize_string_tuple(merchants),
        direction=normalized_direction,
        group_by=normalized_group_by,
        limit=limit,
    )


def validate_required_columns(df: pd.DataFrame) -> None:
    """Validate that the processed dataframe contains the required spend-summary columns."""
    missing_columns = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing_columns:
        raise SpendSummaryInputError(
            f"Input dataframe is missing required columns: {missing_columns}."
        )
##BRICK 3: Filter application functions
def _apply_account_filter(df: pd.DataFrame, account_ids: tuple[str, ...]) -> pd.DataFrame:
    """Filter rows by account IDs when provided."""
    if not account_ids:
        return df

    return df[df["account_id"].isin(account_ids)].copy()


def _apply_category_filter(df: pd.DataFrame, categories: tuple[str, ...]) -> pd.DataFrame:
    """Filter rows by canonical categories when provided."""
    if not categories:
        return df

    return df[df["category"].isin(categories)].copy()


def _apply_merchant_filter(df: pd.DataFrame, merchants: tuple[str, ...]) -> pd.DataFrame:
    """Filter rows by normalized merchant labels when provided."""
    if not merchants:
        return df

    return df[df["merchant"].isin(merchants)].copy()


def _apply_direction_filter(df: pd.DataFrame, direction: str) -> pd.DataFrame:
    """Filter rows by transaction direction."""
    return df[df["direction"] == direction].copy()


def _apply_date_range_filter(
    df: pd.DataFrame,
    start_date: str | None,
    end_date: str | None,
) -> pd.DataFrame:
    """Filter rows by inclusive timestamp range."""
    if start_date is None and end_date is None:
        return df

    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        timestamp_series = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    else:
        timestamp_series = df["timestamp"]

    if timestamp_series.isna().any():
        raise SpendSummaryInputError(
            "Input dataframe contains invalid timestamp values that cannot be filtered safely."
        )

    filtered_df = df.copy()
    filtered_df["timestamp"] = timestamp_series

    if start_date is not None:
        start_ts = pd.Timestamp(start_date, tz="UTC")
        filtered_df = filtered_df[filtered_df["timestamp"] >= start_ts]

    if end_date is not None:
        end_ts = pd.Timestamp(end_date, tz="UTC")
        filtered_df = filtered_df[filtered_df["timestamp"] <= end_ts]

    return filtered_df.copy()


def apply_spend_filters(
    df: pd.DataFrame,
    request: SpendSummaryRequest,
) -> pd.DataFrame:
    """Apply deterministic spend-summary filters in a fixed order."""
    filtered_df = df.copy()

    filtered_df = _apply_account_filter(filtered_df, request.account_ids)
    filtered_df = _apply_date_range_filter(filtered_df, request.start_date, request.end_date)
    filtered_df = _apply_category_filter(filtered_df, request.categories)
    filtered_df = _apply_merchant_filter(filtered_df, request.merchants)
    filtered_df = _apply_direction_filter(filtered_df, request.direction)

    logger.debug(
        "Applied spend summary filters.",
        extra={
            "account_ids_count": len(request.account_ids),
            "categories_count": len(request.categories),
            "merchants_count": len(request.merchants),
            "direction": request.direction,
            "group_by": request.group_by,
            "remaining_rows": len(filtered_df),
        },
    )

    return filtered_df

##BRICK 4: Normalization and safety functions for aggregation
DECIMAL_QUANTIZE_PLACES = Decimal("0.01")
ZERO_DECIMAL = Decimal("0.00")


def _ensure_non_empty_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a defensive copy of the dataframe, preserving empty results safely."""
    if df.empty:
        return df.copy()
    return df.copy()


def _normalize_amount_series(df: pd.DataFrame) -> pd.Series:
    """Normalize transaction amounts into Decimal values for deterministic aggregation."""
    if "amount" not in df.columns:
        raise SpendSummaryInputError("Input dataframe is missing required column: ['amount'].")

    normalized_amounts: list[Decimal] = []

    for raw_value in df["amount"].tolist():
        if pd.isna(raw_value):
            raise SpendSummaryInputError("Input dataframe contains null amount values.")

        try:
            decimal_value = Decimal(str(raw_value)).quantize(DECIMAL_QUANTIZE_PLACES)
        except Exception as exc:  # pragma: no cover
            raise SpendSummaryInputError(
                f"Input dataframe contains invalid amount value: {raw_value!r}."
            ) from exc

        normalized_amounts.append(decimal_value)

    return pd.Series(normalized_amounts, index=df.index, dtype="object")


def _select_valid_spend_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Return rows safe for spend aggregation after filter application."""
    safe_df = _ensure_non_empty_dataframe(df)

    if safe_df.empty:
        safe_df["normalized_amount"] = pd.Series(dtype="object")
        return safe_df

    normalized_amounts = _normalize_amount_series(safe_df)

    safe_df = safe_df.copy()
    safe_df["normalized_amount"] = normalized_amounts

    return safe_df
##BRICK :

##BRICK :

##BRICK :

##BRICK :

##BRICK :