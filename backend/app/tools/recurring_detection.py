# app/tools/recurring_detection.py
# 2026-02-25
"""Purpose: Determine recurring payments.
Duplication alert: coordinate with data_pipeline/recurring_logic.py as mentioned."""

##BRICK 1: Define the purpose and scope of the recurring detection tool, emphasizing its deterministic nature and read-only access to pre-processed recurring payment data. Highlight that it does not perform I/O, LLM calls, RAG retrieval, or mutate the input dataframe.
"""
Deterministic recurring-payment retrieval tool for recurrence-enriched
structured transaction data.

This module reads recurrence fields that were already computed upstream in the
data pipeline. It does not perform I/O, LLM calls, RAG retrieval, or mutation
of the input dataframe.
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

WEEKLY = "weekly"
BIWEEKLY = "biweekly"
MONTHLY = "monthly"
IRREGULAR = "irregular"

LOW = "low"
MEDIUM = "medium"
HIGH = "high"

DEFAULT_LIMIT: int = 25
DEFAULT_SORT_BY: str = "last_seen_timestamp"
DEFAULT_SORT_DESCENDING: bool = True
DEFAULT_DIRECTION: str | None = DEBIT
DEFAULT_INCLUDE_IRREGULAR: bool = True

ALLOWED_DIRECTIONS: frozenset[str] = frozenset({DEBIT, CREDIT})
ALLOWED_CADENCES: frozenset[str] = frozenset(
    {
        WEEKLY,
        BIWEEKLY,
        MONTHLY,
        IRREGULAR,
    }
)
ALLOWED_CONFIDENCES: frozenset[str] = frozenset({LOW, MEDIUM, HIGH})
ALLOWED_SORT_FIELDS: frozenset[str] = frozenset(
    {
        "last_seen_timestamp",
        "first_seen_timestamp",
        "average_amount",
        "merchant",
        "cadence",
        "confidence",
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
        "merchant",
        "category",
        "subcategory",
        "is_recurring",
        "recurrence_cadence",
        "recurrence_confidence",
    }
)


class RecurringDetectionError(Exception):
    """Base exception for recurring detection tool failures."""


class RecurringDetectionInputError(RecurringDetectionError):
    """Raised when recurring detection inputs are invalid."""


@dataclass(frozen=True, slots=True)
class RecurringDetectionRequest:
    """Deterministic request contract for recurring-payment queries."""

    user_id: str | None = None
    account_ids: tuple[str, ...] = ()
    merchants: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    cadences: tuple[str, ...] = ()
    confidences: tuple[str, ...] = ()
    direction: Literal["debit", "credit"] | None = DEFAULT_DIRECTION
    include_irregular: bool = DEFAULT_INCLUDE_IRREGULAR
    start_date: str | None = None
    end_date: str | None = None
    limit: int = DEFAULT_LIMIT
    sort_by: Literal[
        "last_seen_timestamp",
        "first_seen_timestamp",
        "average_amount",
        "merchant",
        "cadence",
        "confidence",
    ] = DEFAULT_SORT_BY
    sort_descending: bool = DEFAULT_SORT_DESCENDING


@dataclass(frozen=True, slots=True)
class RecurringPaymentRecord:
    """Typed recurring-payment output row for downstream orchestration."""

    merchant: str
    category: str
    subcategory: str
    account_id: str
    direction: str
    cadence: str
    confidence: str
    transaction_count: int
    first_seen_timestamp: str
    last_seen_timestamp: str
    average_amount: Decimal
    currency: str | None = None
    is_irregular: bool = False


@dataclass(frozen=True, slots=True)
class RecurringDetectionResult:
    """Structured recurring-payment output for downstream orchestration."""

    records: tuple[RecurringPaymentRecord, ...]
    match_count: int
    summary: dict[str, Any] = field(default_factory=dict)
    applied_filters: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

##BRICK 2: Implement input normalization and validation logic for the recurring detection request. This includes handling various input formats for filters (e.g., single string, list of strings, None) and ensuring that all values conform to expected types and allowed values. Raise descriptive exceptions for invalid inputs.
def _normalize_string_tuple(values: Any) -> tuple[str, ...]:
    """Normalize string-like filter inputs into a clean tuple of strings."""
    if values is None:
        return ()

    if isinstance(values, str):
        candidate_values = [values]
    elif isinstance(values, (list, tuple, set, frozenset)):
        candidate_values = list(values)
    else:
        raise RecurringDetectionInputError(
            "Filter values must be a string, sequence, or None."
        )

    normalized: list[str] = []
    for value in candidate_values:
        if value is None:
            continue
        if not isinstance(value, str):
            raise RecurringDetectionInputError("All filter values must be strings.")
        cleaned = value.strip().lower()
        if cleaned:
            normalized.append(cleaned)

    return tuple(normalized)


def _normalize_boolean(value: Any, field_name: str) -> bool:
    """Normalize a boolean-like request value."""
    if isinstance(value, bool):
        return value

    if value is None:
        raise RecurringDetectionInputError(f"{field_name} must be a boolean.")

    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"true", "1", "yes"}:
            return True
        if cleaned in {"false", "0", "no"}:
            return False

    raise RecurringDetectionInputError(f"{field_name} must be a boolean.")


def normalize_recurring_detection_request(
    *,
    user_id: str | None = None,
    account_ids: Any = None,
    merchants: Any = None,
    categories: Any = None,
    cadences: Any = None,
    confidences: Any = None,
    direction: str | None = DEFAULT_DIRECTION,
    include_irregular: Any = DEFAULT_INCLUDE_IRREGULAR,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = DEFAULT_LIMIT,
    sort_by: str = DEFAULT_SORT_BY,
    sort_descending: bool = DEFAULT_SORT_DESCENDING,
) -> RecurringDetectionRequest:
    """Validate and normalize raw request values into a deterministic recurrence request."""
    cleaned_user_id = user_id.strip() if isinstance(user_id, str) and user_id.strip() else None
    cleaned_start_date = start_date.strip() if isinstance(start_date, str) and start_date.strip() else None
    cleaned_end_date = end_date.strip() if isinstance(end_date, str) and end_date.strip() else None

    normalized_direction: str | None = None
    if direction is not None:
        if not isinstance(direction, str) or not direction.strip():
            raise RecurringDetectionInputError(
                "direction must be a non-empty string when provided."
            )
        normalized_direction = direction.strip().lower()
        if normalized_direction not in ALLOWED_DIRECTIONS:
            raise RecurringDetectionInputError(
                f"Unsupported direction '{direction}'. Allowed values: {sorted(ALLOWED_DIRECTIONS)}."
            )

    if not isinstance(sort_by, str) or not sort_by.strip():
        raise RecurringDetectionInputError("sort_by must be a non-empty string.")
    normalized_sort_by = sort_by.strip()
    if normalized_sort_by not in ALLOWED_SORT_FIELDS:
        raise RecurringDetectionInputError(
            f"Unsupported sort_by '{sort_by}'. Allowed values: {sorted(ALLOWED_SORT_FIELDS)}."
        )

    if not isinstance(sort_descending, bool):
        raise RecurringDetectionInputError("sort_descending must be a boolean.")

    if not isinstance(limit, int):
        raise RecurringDetectionInputError("limit must be an integer.")
    if limit <= 0:
        raise RecurringDetectionInputError("limit must be greater than zero.")

    normalized_cadences = _normalize_string_tuple(cadences)
    invalid_cadences = sorted(set(normalized_cadences).difference(ALLOWED_CADENCES))
    if invalid_cadences:
        raise RecurringDetectionInputError(
            f"Unsupported cadence values: {invalid_cadences}. Allowed values: {sorted(ALLOWED_CADENCES)}."
        )

    normalized_confidences = _normalize_string_tuple(confidences)
    invalid_confidences = sorted(
        set(normalized_confidences).difference(ALLOWED_CONFIDENCES)
    )
    if invalid_confidences:
        raise RecurringDetectionInputError(
            f"Unsupported confidence values: {invalid_confidences}. Allowed values: {sorted(ALLOWED_CONFIDENCES)}."
        )

    if cleaned_start_date and cleaned_end_date and cleaned_start_date > cleaned_end_date:
        raise RecurringDetectionInputError(
            "start_date must be less than or equal to end_date."
        )

    return RecurringDetectionRequest(
        user_id=cleaned_user_id,
        account_ids=_normalize_string_tuple(account_ids),
        merchants=_normalize_string_tuple(merchants),
        categories=_normalize_string_tuple(categories),
        cadences=normalized_cadences,
        confidences=normalized_confidences,
        direction=normalized_direction,
        include_irregular=_normalize_boolean(include_irregular, "include_irregular"),
        start_date=cleaned_start_date,
        end_date=cleaned_end_date,
        limit=limit,
        sort_by=normalized_sort_by,
        sort_descending=sort_descending,
    )


def validate_required_columns(df: pd.DataFrame) -> None:
    """Validate that the processed dataframe contains the required recurrence columns."""
    missing_columns = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing_columns:
        raise RecurringDetectionInputError(
            f"Input dataframe is missing required columns: {missing_columns}."
        )
##BRICK 3: Implement individual filter functions for each of the supported filters (account IDs, merchants, categories, cadences, confidences, direction, date range). Each function should take the dataframe and the relevant filter values as input and return a filtered dataframe. Ensure that the filtering logic is robust to different data types and formats in the input dataframe.
def _apply_account_id_filter(
    df: pd.DataFrame,
    account_ids: tuple[str, ...],
) -> pd.DataFrame:
    """Filter rows by exact account IDs when provided."""
    if not account_ids:
        return df

    return df[df["account_id"].astype(str).isin(account_ids)].copy()


def _apply_merchant_filter(
    df: pd.DataFrame,
    merchants: tuple[str, ...],
) -> pd.DataFrame:
    """Filter rows by exact normalized merchant labels when provided."""
    if not merchants:
        return df

    merchant_series = df["merchant"].astype(str).str.strip().str.lower()
    return df[merchant_series.isin(merchants)].copy()


def _apply_category_filter(
    df: pd.DataFrame,
    categories: tuple[str, ...],
) -> pd.DataFrame:
    """Filter rows by exact canonical categories when provided."""
    if not categories:
        return df

    category_series = df["category"].astype(str).str.strip().str.lower()
    return df[category_series.isin(categories)].copy()


def _apply_cadence_filter(
    df: pd.DataFrame,
    cadences: tuple[str, ...],
) -> pd.DataFrame:
    """Filter rows by recurrence cadence when provided."""
    if not cadences:
        return df

    cadence_series = df["recurrence_cadence"].astype(str).str.strip().str.lower()
    return df[cadence_series.isin(cadences)].copy()


def _apply_confidence_filter(
    df: pd.DataFrame,
    confidences: tuple[str, ...],
) -> pd.DataFrame:
    """Filter rows by recurrence confidence when provided."""
    if not confidences:
        return df

    confidence_series = df["recurrence_confidence"].astype(str).str.strip().str.lower()
    return df[confidence_series.isin(confidences)].copy()


def _apply_direction_filter(
    df: pd.DataFrame,
    direction: str | None,
) -> pd.DataFrame:
    """Filter rows by transaction direction when provided."""
    if direction is None:
        return df

    direction_series = df["direction"].astype(str).str.strip().str.lower()
    return df[direction_series == direction].copy()


def _apply_date_range_filter(
    df: pd.DataFrame,
    start_date: str | None,
    end_date: str | None,
) -> pd.DataFrame:
    """Filter rows by inclusive timestamp range."""
    if start_date is None and end_date is None:
        return df

    timestamp_series = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    if timestamp_series.isna().any():
        raise RecurringDetectionInputError(
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


def _select_recurring_rows(
    df: pd.DataFrame,
    *,
    include_irregular: bool,
) -> pd.DataFrame:
    """Restrict rows to recurrence-enriched rows marked as recurring."""
    recurring_mask = df["is_recurring"].astype(bool)
    recurring_df = df[recurring_mask].copy()

    if include_irregular:
        return recurring_df

    cadence_series = recurring_df["recurrence_cadence"].astype(str).str.strip().str.lower()
    return recurring_df[cadence_series != IRREGULAR].copy()


def apply_recurring_filters(
    df: pd.DataFrame,
    request: RecurringDetectionRequest,
) -> pd.DataFrame:
    """Apply deterministic recurring-payment filters in a fixed order."""
    filtered_df = df.copy()

    filtered_df = _select_recurring_rows(
        filtered_df,
        include_irregular=request.include_irregular,
    )
    filtered_df = _apply_account_id_filter(filtered_df, request.account_ids)
    filtered_df = _apply_merchant_filter(filtered_df, request.merchants)
    filtered_df = _apply_category_filter(filtered_df, request.categories)
    filtered_df = _apply_cadence_filter(filtered_df, request.cadences)
    filtered_df = _apply_confidence_filter(filtered_df, request.confidences)
    filtered_df = _apply_direction_filter(filtered_df, request.direction)
    filtered_df = _apply_date_range_filter(
        filtered_df,
        request.start_date,
        request.end_date,
    )

    logger.debug(
        "Applied recurring detection filters.",
        extra={
            "account_ids_count": len(request.account_ids),
            "merchants_count": len(request.merchants),
            "categories_count": len(request.categories),
            "cadences_count": len(request.cadences),
            "confidences_count": len(request.confidences),
            "direction": request.direction,
            "include_irregular": request.include_irregular,
            "remaining_rows": len(filtered_df),
        },
    )

    return filtered_df

##BRICK 4: Implement the sorting logic for the filtered recurring payment records. This should include a stable sorting mechanism that can handle tie-breaking based on multiple fields to ensure deterministic output. The sorting should be flexible to allow sorting by different fields as specified in the request.
DECIMAL_QUANTIZE_PLACES = Decimal("0.01")
ZERO_DECIMAL = Decimal("0.00")


def _ensure_non_empty_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a defensive copy of the dataframe, preserving empty results safely."""
    return df.copy()


def _normalize_timestamp_series(values: pd.Series, field_name: str) -> pd.Series:
    """Normalize timestamp-like values into timezone-aware UTC timestamps."""
    normalized = pd.to_datetime(values, errors="coerce", utc=True)
    if normalized.isna().any():
        raise RecurringDetectionInputError(
            f"Encountered invalid timestamp values in field '{field_name}'."
        )
    return normalized


def _sort_recurring_rows_for_aggregation(df: pd.DataFrame) -> pd.DataFrame:
    """Sort filtered recurring rows into a stable deterministic order before aggregation."""
    sortable_df = _ensure_non_empty_dataframe(df)

    if sortable_df.empty:
        return sortable_df

    sortable_df["timestamp"] = _normalize_timestamp_series(
        sortable_df["timestamp"],
        "timestamp",
    )

    return sortable_df.sort_values(
        by=[
            "merchant",
            "account_id",
            "direction",
            "recurrence_cadence",
            "recurrence_confidence",
            "timestamp",
            "transaction_id",
        ],
        ascending=[True, True, True, True, True, True, True],
        kind="mergesort",
    ).copy()


def sort_recurring_payment_records(
    records: tuple[RecurringPaymentRecord, ...],
    *,
    sort_by: str,
    sort_descending: bool,
) -> tuple[RecurringPaymentRecord, ...]:
    """Sort aggregated recurring payment records deterministically."""
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise RecurringDetectionInputError(
            f"Unsupported sort_by '{sort_by}'. Allowed values: {sorted(ALLOWED_SORT_FIELDS)}."
        )

    if not records:
        return ()

    def _record_sort_key(record: RecurringPaymentRecord) -> tuple[Any, ...]:
        if sort_by == "last_seen_timestamp":
            return (
                pd.Timestamp(record.last_seen_timestamp),
                record.merchant.lower(),
                record.account_id.lower(),
            )

        if sort_by == "first_seen_timestamp":
            return (
                pd.Timestamp(record.first_seen_timestamp),
                record.merchant.lower(),
                record.account_id.lower(),
            )

        if sort_by == "average_amount":
            return (
                record.average_amount,
                record.merchant.lower(),
                record.account_id.lower(),
            )

        if sort_by == "merchant":
            return (
                record.merchant.lower(),
                record.account_id.lower(),
                pd.Timestamp(record.last_seen_timestamp),
            )

        if sort_by == "cadence":
            return (
                record.cadence.lower(),
                record.merchant.lower(),
                record.account_id.lower(),
            )

        if sort_by == "confidence":
            return (
                record.confidence.lower(),
                record.merchant.lower(),
                record.account_id.lower(),
            )

        raise RecurringDetectionInputError(
            f"Unsupported sort_by '{sort_by}'. Allowed values: {sorted(ALLOWED_SORT_FIELDS)}."
        )

    return tuple(
        sorted(
            records,
            key=_record_sort_key,
            reverse=sort_descending,
        )
    )

##BRICK 5: Implement the aggregation logic to combine individual recurring payment rows into cohesive recurring payment records. This should include logic to compute aggregate fields such as average amount, first and last seen timestamps, and transaction count for each recurring payment stream. Ensure that the aggregation is deterministic and handles edge cases gracefully (e.g., groups with a single transaction, missing or null values).
def _normalize_amount_field(value: Any) -> Decimal:
    """Normalize an amount-like value into a quantized Decimal."""
    if pd.isna(value):
        raise RecurringDetectionInputError("Encountered null amount value in recurring rows.")

    try:
        return Decimal(str(value)).quantize(DECIMAL_QUANTIZE_PLACES)
    except Exception as exc:  # pragma: no cover
        raise RecurringDetectionInputError(
            f"Encountered invalid amount value in recurring rows: {value!r}."
        ) from exc


def _sum_decimal_values(values: list[Decimal]) -> Decimal:
    """Sum Decimal values deterministically."""
    total = ZERO_DECIMAL
    for value in values:
        total += value
    return total.quantize(DECIMAL_QUANTIZE_PLACES)


def _average_decimal_values(values: list[Decimal]) -> Decimal:
    """Compute a deterministic quantized Decimal average."""
    if not values:
        return ZERO_DECIMAL

    total = _sum_decimal_values(values)
    average = total / Decimal(len(values))
    return average.quantize(DECIMAL_QUANTIZE_PLACES)


def _build_recurring_group_key(row: pd.Series) -> tuple[str, ...]:
    """Build a deterministic grouping key for one recurring payment stream."""
    return (
        str(row["merchant"]).strip(),
        str(row["category"]).strip(),
        str(row["subcategory"]).strip(),
        str(row["account_id"]).strip(),
        str(row["direction"]).strip(),
        str(row["recurrence_cadence"]).strip(),
        str(row["recurrence_confidence"]).strip(),
    )


def _build_recurring_payment_record(group_df: pd.DataFrame) -> RecurringPaymentRecord:
    """Aggregate one recurring stream dataframe into a typed recurring payment record."""
    if group_df.empty:
        raise RecurringDetectionInputError("Cannot build recurring payment record from empty group.")

    sorted_group_df = group_df.sort_values(
        by=["timestamp", "transaction_id"],
        ascending=[True, True],
        kind="mergesort",
    ).copy()

    first_row = sorted_group_df.iloc[0]
    last_row = sorted_group_df.iloc[-1]

    normalized_amounts = [
        _normalize_amount_field(value)
        for value in sorted_group_df["amount"].tolist()
    ]

    currencies = {
        str(value).strip()
        for value in sorted_group_df["currency"].tolist()
        if str(value).strip()
    }
    if not currencies:
        raise RecurringDetectionInputError(
            "Recurring payment group contains no valid currency values."
        )

    cadence = str(first_row["recurrence_cadence"]).strip().lower()
    confidence = str(first_row["recurrence_confidence"]).strip().lower()

    return RecurringPaymentRecord(
        merchant=str(first_row["merchant"]).strip(),
        category=str(first_row["category"]).strip(),
        subcategory=str(first_row["subcategory"]).strip(),
        account_id=str(first_row["account_id"]).strip(),
        direction=str(first_row["direction"]).strip().lower(),
        cadence=cadence,
        confidence=confidence,
        transaction_count=int(len(sorted_group_df)),
        first_seen_timestamp=pd.Timestamp(first_row["timestamp"]).isoformat(),
        last_seen_timestamp=pd.Timestamp(last_row["timestamp"]).isoformat(),
        average_amount=_average_decimal_values(normalized_amounts),
        currency=next(iter(currencies)) if len(currencies) == 1 else None,
        is_irregular=(cadence == IRREGULAR),
    )


def aggregate_recurring_payment_records(
    df: pd.DataFrame,
) -> tuple[RecurringPaymentRecord, ...]:
    """Aggregate filtered recurring rows into deterministic recurring payment records."""
    if df.empty:
        return ()

    sorted_df = _sort_recurring_rows_for_aggregation(df)

    grouped_frames: dict[tuple[str, ...], list[int]] = {}
    for idx, row in sorted_df.iterrows():
        group_key = _build_recurring_group_key(row)
        grouped_frames.setdefault(group_key, []).append(idx)

    records: list[RecurringPaymentRecord] = []
    for group_key in sorted(grouped_frames):
        group_df = sorted_df.loc[grouped_frames[group_key]].copy()
        records.append(_build_recurring_payment_record(group_df))

    return tuple(records)


def limit_recurring_payment_records(
    records: tuple[RecurringPaymentRecord, ...],
    *,
    limit: int,
) -> tuple[RecurringPaymentRecord, ...]:
    """Limit recurring payment records deterministically after final sorting."""
    if limit <= 0:
        raise RecurringDetectionInputError("limit must be greater than zero.")

    return records[:limit]

##BRICK 6: Implement the logic to build summary metadata and warnings based on the resulting recurring payment records. The summary should include counts of records by cadence, confidence, and currency. Warnings should be generated for edge cases such as no matching records, multiple currencies, or all records being irregular.
def build_recurring_summary(
    records: tuple[RecurringPaymentRecord, ...],
) -> dict[str, Any]:
    """Build structured summary metadata from recurring payment records."""
    cadence_counts: dict[str, int] = {}
    confidence_counts: dict[str, int] = {}
    currency_counts: dict[str, int] = {}

    for record in records:
        cadence_counts[record.cadence] = cadence_counts.get(record.cadence, 0) + 1
        confidence_counts[record.confidence] = (
            confidence_counts.get(record.confidence, 0) + 1
        )

        currency_key = record.currency if record.currency is not None else "mixed"
        currency_counts[currency_key] = currency_counts.get(currency_key, 0) + 1

    return {
        "count_by_cadence": dict(sorted(cadence_counts.items(), key=lambda item: item[0])),
        "count_by_confidence": dict(sorted(confidence_counts.items(), key=lambda item: item[0])),
        "count_by_currency": dict(sorted(currency_counts.items(), key=lambda item: item[0])),
    }


def build_recurring_warnings(
    records: tuple[RecurringPaymentRecord, ...],
) -> tuple[str, ...]:
    """Build deterministic warnings for recurring payment results."""
    warnings: list[str] = []

    if not records:
        warnings.append("No recurring payments matched the provided filters.")
        return tuple(warnings)

    currencies = {record.currency for record in records if record.currency is not None}
    has_mixed_currency_groups = any(record.currency is None for record in records)

    if len(currencies) > 1 or has_mixed_currency_groups:
        warnings.append(
            "Multiple or mixed currencies detected in recurring payment results. Values should not be combined implicitly."
        )

    if all(record.is_irregular for record in records):
        warnings.append(
            "All returned recurring payment records are marked as irregular."
        )

    return tuple(warnings)


def build_applied_filters(
    request: RecurringDetectionRequest,
) -> dict[str, Any]:
    """Build an audit-safe view of the applied recurring-payment filters."""
    return {
        "user_id": request.user_id,
        "account_ids": request.account_ids,
        "merchants": request.merchants,
        "categories": request.categories,
        "cadences": request.cadences,
        "confidences": request.confidences,
        "direction": request.direction,
        "include_irregular": request.include_irregular,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "limit": request.limit,
        "sort_by": request.sort_by,
        "sort_descending": request.sort_descending,
    }

##BRICK 7: Implement the main orchestration function that ties together all the components: input validation, filtering, aggregation, sorting, and summary/warning generation. Ensure that the function is robust to edge cases and provides clear logging for debugging and audit purposes.
def detect_recurring_payments(
    df: pd.DataFrame,
    request: RecurringDetectionRequest,
) -> RecurringDetectionResult:
    """Run the deterministic recurring-payment tool on a recurrence-enriched dataframe."""
    validate_required_columns(df)

    filtered_df = apply_recurring_filters(df, request)
    records = aggregate_recurring_payment_records(filtered_df)
    sorted_records = sort_recurring_payment_records(
        records,
        sort_by=request.sort_by,
        sort_descending=request.sort_descending,
    )
    limited_records = limit_recurring_payment_records(
        sorted_records,
        limit=request.limit,
    )

    summary = build_recurring_summary(limited_records)
    warnings = build_recurring_warnings(limited_records)
    applied_filters = build_applied_filters(request)

    logger.info(
        "Recurring payment detection computed successfully.",
        extra={
            "rows_in": len(df),
            "rows_after_filters": len(filtered_df),
            "record_count_before_limit": len(records),
            "record_count_after_limit": len(limited_records),
            "sort_by": request.sort_by,
            "sort_descending": request.sort_descending,
            "include_irregular": request.include_irregular,
        },
    )

    return RecurringDetectionResult(
        records=limited_records,
        match_count=len(limited_records),
        summary=summary,
        applied_filters=applied_filters,
        warnings=warnings,
    )

##BRICK 8: Implement a serialization function to convert the recurring detection result into a JSON-friendly dictionary format.
#  This should handle the conversion of complex types (e.g., Decimal, timestamps) into standard JSON types and ensure that the output is deterministic and consistent.
def recurring_detection_result_to_dict(
    result: RecurringDetectionResult,
) -> dict[str, Any]:
    """Serialize a recurring detection result into a JSON-friendly dictionary."""
    return {
        "records": [
            {
                "merchant": record.merchant,
                "category": record.category,
                "subcategory": record.subcategory,
                "account_id": record.account_id,
                "direction": record.direction,
                "cadence": record.cadence,
                "confidence": record.confidence,
                "transaction_count": record.transaction_count,
                "first_seen_timestamp": record.first_seen_timestamp,
                "last_seen_timestamp": record.last_seen_timestamp,
                "average_amount": str(record.average_amount),
                "currency": record.currency,
                "is_irregular": record.is_irregular,
            }
            for record in result.records
        ],
        "match_count": result.match_count,
        "summary": dict(result.summary),
        "applied_filters": dict(result.applied_filters),
        "warnings": list(result.warnings),
    }
