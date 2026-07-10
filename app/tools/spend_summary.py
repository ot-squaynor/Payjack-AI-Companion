# app/tools/spend_summary.py
# 2026-02-25
"""Purpose: Deterministic aggregation (category totals, merchants, trends).
Critical rule: LLM must not change these outputs."""
from __future__ import annotations

##BRICK 1: Context and imports
# Deterministic spend summary tool for structured transaction data.
# This module computes read-only spend aggregates from already-processed
# transaction datasets. It does not perform I/O, LLM calls, RAG retrieval,
# or any mutation of the input dataframe.

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

import logging

import pandas as pd

logger = logging.getLogger(__name__)

DEBIT = "debit"
CREDIT = "credit"
MOMO = "momo"

DEFAULT_DIRECTION: str = DEBIT
DEFAULT_GROUP_LIMIT: int = 10
DEFAULT_SORT_DESCENDING: bool = True

ALLOWED_DIRECTIONS: frozenset[str] = frozenset({DEBIT, CREDIT, MOMO}) # Only allow explicit direction filtering for clarity and deterministic output structure.

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
    """Base exception for spend summary tool failures.""" # General catch-all for any unexpected issues during processing, with more specific subclasses for input validation errors.


class SpendSummaryInputError(SpendSummaryError):
    """Raised when spend summary inputs are invalid.""" # Raised for any issues with the input dataframe or request parameters that would prevent safe and deterministic summarization.


@dataclass(frozen=True, slots=True)
class SpendSummaryRequest:
    """Deterministic request contract for spend summary queries.""" # Encapsulates all normalized and validated parameters for a spend summary query, ensuring a consistent interface for the summarization logic and downstream orchestration.

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

##BRICK 5: Aggregation and breakdown functions
def _sum_decimal_values(values: list[Decimal]) -> Decimal:
    """Sum Decimal values deterministically."""
    total = ZERO_DECIMAL
    for value in values:
        total += value
    return total.quantize(DECIMAL_QUANTIZE_PLACES)


def _count_transactions(df: pd.DataFrame) -> int:
    """Count transactions in the filtered spend dataframe."""
    return int(len(df.index))


def build_currency_breakdown(df: pd.DataFrame) -> dict[str, Decimal]:
    """Build a deterministic spend breakdown by currency."""
    if df.empty:
        return {}

    currency_totals: dict[str, list[Decimal]] = {}

    for _, row in df.iterrows():
        currency = str(row["currency"]).strip()
        if not currency:
            raise SpendSummaryInputError("Input dataframe contains blank currency values.")

        amount = row["normalized_amount"]
        if not isinstance(amount, Decimal):
            raise SpendSummaryInputError("normalized_amount must contain Decimal values.")

        currency_totals.setdefault(currency, []).append(amount)

    return {
        currency: _sum_decimal_values(amounts)
        for currency, amounts in sorted(currency_totals.items(), key=lambda item: item[0])
    }


def aggregate_total_spend(df: pd.DataFrame) -> Decimal:
    """Aggregate total spend across all filtered spend rows."""
    if df.empty:
        return ZERO_DECIMAL

    amounts = df["normalized_amount"].tolist()
    if any(not isinstance(amount, Decimal) for amount in amounts):
        raise SpendSummaryInputError("normalized_amount must contain Decimal values.")

    return _sum_decimal_values(amounts)


def build_spend_warnings(currency_breakdown: dict[str, Decimal]) -> tuple[str, ...]:
    """Build deterministic warnings for potentially ambiguous summary output."""
    warnings: list[str] = []

    if len(currency_breakdown) > 1:
        warnings.append(
            "Multiple currencies detected. Totals are separated by currency and should not be combined implicitly."
        )

    return tuple(warnings)

##BRICK 6: Grouping key construction and grouped aggregation
def _build_group_key_series(df: pd.DataFrame, group_by: str) -> pd.Series:
    """Build a deterministic grouping key series for the requested dimension."""
    if group_by == "category":
        return df["category"].astype(str)

    if group_by == "subcategory":
        return df["subcategory"].astype(str)

    if group_by == "merchant":
        return df["merchant"].astype(str)

    if group_by == "account":
        return df["account_id"].astype(str)

    if group_by == "currency":
        return df["currency"].astype(str)

    if group_by == "month":
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            timestamp_series = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        else:
            timestamp_series = df["timestamp"]

        if timestamp_series.isna().any():
            raise SpendSummaryInputError(
                "Input dataframe contains invalid timestamp values that cannot be grouped by month safely."
            )

        return timestamp_series.dt.strftime("%Y-%m")

    raise SpendSummaryInputError(
        f"Unsupported group_by '{group_by}'. Allowed values: {sorted(ALLOWED_GROUP_BY)}."
    )


def aggregate_grouped_spend(
    df: pd.DataFrame,
    *,
    group_by: str | None,
    limit: int,
    sort_descending: bool = DEFAULT_SORT_DESCENDING,
) -> tuple[GroupedSpendRow, ...]:
    """Aggregate spend deterministically by the requested grouping dimension."""
    if group_by is None or df.empty:
        return ()

    if group_by not in ALLOWED_GROUP_BY:
        raise SpendSummaryInputError(
            f"Unsupported group_by '{group_by}'. Allowed values: {sorted(ALLOWED_GROUP_BY)}."
        )

    if limit <= 0:
        raise SpendSummaryInputError("limit must be greater than zero.")

    group_key_series = _build_group_key_series(df, group_by)

    grouped_amounts: dict[str, list[Decimal]] = {}
    grouped_counts: dict[str, int] = {}
    grouped_currencies: dict[str, set[str]] = {}

    for idx, group_key in group_key_series.items():
        normalized_key = str(group_key).strip()
        if not normalized_key:
            normalized_key = "unknown"

        amount = df.at[idx, "normalized_amount"]
        currency = str(df.at[idx, "currency"]).strip()

        if not isinstance(amount, Decimal):
            raise SpendSummaryInputError("normalized_amount must contain Decimal values.")

        if not currency:
            raise SpendSummaryInputError("Input dataframe contains blank currency values.")

        grouped_amounts.setdefault(normalized_key, []).append(amount)
        grouped_counts[normalized_key] = grouped_counts.get(normalized_key, 0) + 1
        grouped_currencies.setdefault(normalized_key, set()).add(currency)

    grouped_rows: list[GroupedSpendRow] = []
    for key in grouped_amounts:
        currencies = grouped_currencies[key]
        currency_value = next(iter(currencies)) if len(currencies) == 1 else None

        grouped_rows.append(
            GroupedSpendRow(
                key=key,
                total_amount=_sum_decimal_values(grouped_amounts[key]),
                transaction_count=grouped_counts[key],
                currency=currency_value,
            )
        )

    grouped_rows.sort(
        key=lambda row: (
            row.total_amount,
            row.transaction_count,
            row.key.lower(),
        ),
        reverse=sort_descending,
    )

    return tuple(grouped_rows[:limit])
##BRICK 7: Main summarization function
def summarize_spend(
    df: pd.DataFrame,
    request: SpendSummaryRequest,
) -> SpendSummaryResult:
    """Run the deterministic spend summary tool on a processed transaction dataframe."""
    validate_required_columns(df)

    filtered_df = apply_spend_filters(df, request)
    spend_df = _select_valid_spend_rows(filtered_df)

    total_amount = aggregate_total_spend(spend_df)
    transaction_count = _count_transactions(spend_df)
    currency_breakdown = build_currency_breakdown(spend_df)
    grouped_breakdown = aggregate_grouped_spend(
        spend_df,
        group_by=request.group_by,
        limit=request.limit,
    )
    warnings = build_spend_warnings(currency_breakdown)

    applied_filters: dict[str, Any] = {
        "user_id": request.user_id,
        "account_ids": request.account_ids,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "categories": request.categories,
        "merchants": request.merchants,
        "direction": request.direction,
        "group_by": request.group_by,
        "limit": request.limit,
    }

    logger.info(
        "Spend summary computed successfully.",
        extra={
            "rows_in": len(df),
            "rows_after_filters": len(filtered_df),
            "transaction_count": transaction_count,
            "group_by": request.group_by,
            "currency_count": len(currency_breakdown),
        },
    )

    return SpendSummaryResult(
        total_amount=total_amount,
        transaction_count=transaction_count,
        currency_breakdown=currency_breakdown,
        grouped_breakdown=grouped_breakdown,
        applied_filters=applied_filters,
        warnings=warnings,
    )
##BRICK 8: Serialization function for downstream orchestration
def spend_summary_result_to_dict(result: SpendSummaryResult) -> dict[str, Any]:
    """Serialize a spend summary result into a JSON-friendly dictionary."""
    return {
        "total_amount": str(result.total_amount),
        "transaction_count": result.transaction_count,
        "currency_breakdown": {
            currency: str(amount)
            for currency, amount in result.currency_breakdown.items()
        },
        "grouped_breakdown": [
            {
                "key": row.key,
                "total_amount": str(row.total_amount),
                "transaction_count": row.transaction_count,
                "currency": row.currency,
            }
            for row in result.grouped_breakdown
        ],
        "applied_filters": dict(result.applied_filters),
        "warnings": list(result.warnings),
    }
##BRICK :
