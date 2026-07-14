# app/tools/transaction_lookup.py
# 2026-02-25
"""Purpose: Fetch transactions (by user, time window, filters).
Audit note: Must enforce access control here or in a shared data access layer."""

from __future__ import annotations

##BRICK 1: Define the purpose and scope of the transaction lookup tool, emphasizing its deterministic nature and read-only access to pre-processed transaction data. Highlight that it does not perform I/O, LLM calls, RAG retrieval, or mutate the input dataframe.
# Deterministic transaction lookup tool for structured transaction data.
# This module retrieves read-only transaction records from already-processed
# transaction datasets. It does not perform I/O, LLM calls, RAG retrieval,
# or mutation of the input dataframe.

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

import logging

import pandas as pd

logger = logging.getLogger(__name__)

DEBIT = "debit"
CREDIT = "credit"

DEFAULT_LIMIT: int = 25
DEFAULT_SORT_BY: str = "timestamp"
DEFAULT_SORT_DESCENDING: bool = True
LIMIT_POSITIVE_ERROR = "limit must be greater than zero."

ALLOWED_DIRECTIONS: frozenset[str] = frozenset({DEBIT, CREDIT})
ALLOWED_SORT_FIELDS: frozenset[str] = frozenset(
    {
        "timestamp",
        "amount",
        "merchant",
        "category",
        "account_id",
        "transaction_id",
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
    }
)


class TransactionLookupError(Exception):
    """Base exception for transaction lookup tool failures."""


class TransactionLookupInputError(TransactionLookupError):
    """Raised when transaction lookup inputs are invalid."""


@dataclass(frozen=True, slots=True)
class TransactionLookupRequest:
    """Deterministic request contract for transaction lookup queries."""

    user_id: str | None = None
    transaction_ids: tuple[str, ...] = ()
    account_ids: tuple[str, ...] = ()
    merchants: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    direction: Literal["debit", "credit"] | None = None
    start_date: str | None = None
    end_date: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    limit: int = DEFAULT_LIMIT
    sort_by: Literal[
        "timestamp",
        "amount",
        "merchant",
        "category",
        "account_id",
        "transaction_id",
    ] = DEFAULT_SORT_BY
    sort_descending: bool = DEFAULT_SORT_DESCENDING


@dataclass(frozen=True, slots=True)
class TransactionRecord:
    """Typed transaction output row for downstream orchestration."""

    transaction_id: str
    account_id: str
    timestamp: str
    amount: Decimal
    currency: str
    direction: str
    merchant: str
    category: str
    subcategory: str


@dataclass(frozen=True, slots=True)
class TransactionLookupResult:
    """Structured transaction lookup output for downstream orchestration."""

    records: tuple[TransactionRecord, ...]
    match_count: int
    applied_filters: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


##BRICK 2: Implement normalization functions for string-like filter inputs and decimal amount bounds. These functions ensure that the transaction lookup request is constructed with clean, validated, and appropriately typed values, ready for deterministic querying against the transaction dataset.
DECIMAL_QUANTIZE_PLACES = Decimal("0.01")


def _normalize_string_tuple(values: Any) -> tuple[str, ...]:
    """Normalize string-like filter inputs into a clean tuple of strings."""
    if values is None:
        return ()

    if isinstance(values, str):
        candidate_values = [values]
    elif isinstance(values, (list, tuple, set, frozenset)):
        candidate_values = list(values)
    else:
        raise TransactionLookupInputError(
            "Filter values must be a string, sequence, or None."
        )

    normalized: list[str] = []
    for value in candidate_values:
        if value is None:
            continue
        if not isinstance(value, str):
            raise TransactionLookupInputError("All filter values must be strings.")
        cleaned = value.strip()
        if cleaned:
            normalized.append(cleaned)

    return tuple(normalized)


def _normalize_decimal(value: Any, field_name: str) -> Decimal | None:
    """Normalize an optional amount-bound value into a quantized Decimal."""
    if value is None:
        return None

    try:
        normalized = Decimal(str(value)).quantize(DECIMAL_QUANTIZE_PLACES)
    except Exception as exc:  # pragma: no cover
        raise TransactionLookupInputError(
            f"{field_name} must be a valid decimal-compatible value."
        ) from exc

    return normalized


def _clean_optional_string(value: str | None) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _normalize_direction(direction: str | None) -> str | None:
    if direction is None:
        return None
    if not isinstance(direction, str) or not direction.strip():
        raise TransactionLookupInputError(
            "direction must be a non-empty string when provided."
        )
    normalized_direction = direction.strip().lower()
    if normalized_direction not in ALLOWED_DIRECTIONS:
        raise TransactionLookupInputError(
            f"Unsupported direction '{direction}'. Allowed values: {sorted(ALLOWED_DIRECTIONS)}."
        )
    return normalized_direction


def _normalize_sort_options(sort_by: str, sort_descending: bool) -> tuple[str, bool]:
    if not isinstance(sort_by, str) or not sort_by.strip():
        raise TransactionLookupInputError("sort_by must be a non-empty string.")
    normalized_sort_by = sort_by.strip()
    if normalized_sort_by not in ALLOWED_SORT_FIELDS:
        raise TransactionLookupInputError(
            f"Unsupported sort_by '{sort_by}'. Allowed values: {sorted(ALLOWED_SORT_FIELDS)}."
        )
    if not isinstance(sort_descending, bool):
        raise TransactionLookupInputError("sort_descending must be a boolean.")
    return normalized_sort_by, sort_descending


def _validate_positive_limit(limit: int) -> None:
    if not isinstance(limit, int):
        raise TransactionLookupInputError("limit must be an integer.")
    if limit <= 0:
        raise TransactionLookupInputError(LIMIT_POSITIVE_ERROR)


def _validate_date_order(start_date: str | None, end_date: str | None) -> None:
    if start_date and end_date and start_date > end_date:
        raise TransactionLookupInputError(
            "start_date must be less than or equal to end_date."
        )


def _validate_amount_order(
    min_amount: Decimal | None,
    max_amount: Decimal | None,
) -> None:
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise TransactionLookupInputError(
            "min_amount must be less than or equal to max_amount."
        )


def normalize_transaction_lookup_request(
    *,
    user_id: str | None = None,
    transaction_ids: Any = None,
    account_ids: Any = None,
    merchants: Any = None,
    categories: Any = None,
    direction: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    min_amount: Any = None,
    max_amount: Any = None,
    limit: int = DEFAULT_LIMIT,
    sort_by: str = DEFAULT_SORT_BY,
    sort_descending: bool = DEFAULT_SORT_DESCENDING,
) -> TransactionLookupRequest:
    """Validate and normalize raw request values into a deterministic lookup request."""
    cleaned_user_id = _clean_optional_string(user_id)
    cleaned_start_date = _clean_optional_string(start_date)
    cleaned_end_date = _clean_optional_string(end_date)
    normalized_direction = _normalize_direction(direction)
    normalized_sort_by, normalized_sort_descending = _normalize_sort_options(
        sort_by,
        sort_descending,
    )
    _validate_positive_limit(limit)
    normalized_min_amount = _normalize_decimal(min_amount, "min_amount")
    normalized_max_amount = _normalize_decimal(max_amount, "max_amount")
    _validate_date_order(cleaned_start_date, cleaned_end_date)
    _validate_amount_order(normalized_min_amount, normalized_max_amount)

    return TransactionLookupRequest(
        user_id=cleaned_user_id,
        transaction_ids=_normalize_string_tuple(transaction_ids),
        account_ids=_normalize_string_tuple(account_ids),
        merchants=_normalize_string_tuple(merchants),
        categories=_normalize_string_tuple(categories),
        direction=normalized_direction,
        start_date=cleaned_start_date,
        end_date=cleaned_end_date,
        min_amount=normalized_min_amount,
        max_amount=normalized_max_amount,
        limit=limit,
        sort_by=normalized_sort_by,
        sort_descending=normalized_sort_descending,
    )


def validate_required_columns(df: pd.DataFrame) -> None:
    """Validate that the processed dataframe contains the required lookup columns."""
    missing_columns = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing_columns:
        raise TransactionLookupInputError(
            f"Input dataframe is missing required columns: {missing_columns}."
        )
##BRICK 3: Implement individual filter application functions for each supported filter type (transaction ID, account ID, merchant, category, direction, date range, amount range). Each function takes the current dataframe and the relevant filter values, applies the filter if values are provided, and returns a new filtered dataframe. These functions are designed to be composable and are called in a fixed order by the main filter application function.
def _apply_transaction_id_filter(
    df: pd.DataFrame,
    transaction_ids: tuple[str, ...],
) -> pd.DataFrame:
    """Filter rows by exact transaction IDs when provided."""
    if not transaction_ids:
        return df

    return df[df["transaction_id"].isin(transaction_ids)].copy()


def _apply_account_id_filter(
    df: pd.DataFrame,
    account_ids: tuple[str, ...],
) -> pd.DataFrame:
    """Filter rows by exact account IDs when provided."""
    if not account_ids:
        return df

    return df[df["account_id"].isin(account_ids)].copy()


def _apply_merchant_filter(
    df: pd.DataFrame,
    merchants: tuple[str, ...],
) -> pd.DataFrame:
    """Filter rows by exact normalized merchant labels when provided."""
    if not merchants:
        return df

    return df[df["merchant"].isin(merchants)].copy()


def _apply_category_filter(
    df: pd.DataFrame,
    categories: tuple[str, ...],
) -> pd.DataFrame:
    """Filter rows by exact canonical categories when provided."""
    if not categories:
        return df

    return df[df["category"].isin(categories)].copy()


def _apply_direction_filter(
    df: pd.DataFrame,
    direction: str | None,
) -> pd.DataFrame:
    """Filter rows by transaction direction when provided."""
    if direction is None:
        return df

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
        raise TransactionLookupInputError(
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


def _apply_amount_range_filter(
    df: pd.DataFrame,
    min_amount: Decimal | None,
    max_amount: Decimal | None,
) -> pd.DataFrame:
    """Filter rows by inclusive quantized Decimal amount bounds."""
    if min_amount is None and max_amount is None:
        return df

    normalized_amounts: list[Decimal] = []
    for raw_value in df["amount"].tolist():
        if pd.isna(raw_value):
            raise TransactionLookupInputError(
                "Input dataframe contains null amount values."
            )

        try:
            normalized_amount = Decimal(str(raw_value)).quantize(DECIMAL_QUANTIZE_PLACES)
        except Exception as exc:  # pragma: no cover
            raise TransactionLookupInputError(
                f"Input dataframe contains invalid amount value: {raw_value!r}."
            ) from exc

        normalized_amounts.append(normalized_amount)

    filtered_df = df.copy()
    filtered_df["_normalized_amount"] = pd.Series(
        normalized_amounts,
        index=filtered_df.index,
        dtype="object",
    )

    if min_amount is not None:
        filtered_df = filtered_df[filtered_df["_normalized_amount"] >= min_amount]

    if max_amount is not None:
        filtered_df = filtered_df[filtered_df["_normalized_amount"] <= max_amount]

    return filtered_df.drop(columns=["_normalized_amount"]).copy()


def apply_transaction_lookup_filters(
    df: pd.DataFrame,
    request: TransactionLookupRequest,
) -> pd.DataFrame:
    """Apply deterministic transaction lookup filters in a fixed order."""
    filtered_df = df.copy()

    filtered_df = _apply_transaction_id_filter(filtered_df, request.transaction_ids)
    filtered_df = _apply_account_id_filter(filtered_df, request.account_ids)
    filtered_df = _apply_merchant_filter(filtered_df, request.merchants)
    filtered_df = _apply_category_filter(filtered_df, request.categories)
    filtered_df = _apply_direction_filter(filtered_df, request.direction)
    filtered_df = _apply_date_range_filter(
        filtered_df,
        request.start_date,
        request.end_date,
    )
    filtered_df = _apply_amount_range_filter(
        filtered_df,
        request.min_amount,
        request.max_amount,
    )

    logger.debug(
        "Applied transaction lookup filters.",
        extra={
            "transaction_ids_count": len(request.transaction_ids),
            "account_ids_count": len(request.account_ids),
            "merchants_count": len(request.merchants),
            "categories_count": len(request.categories),
            "direction": request.direction,
            "sort_by": request.sort_by,
            "remaining_rows": len(filtered_df),
        },
    )

    return filtered_df

##BRICK 4: Implement sorting and limiting functions for the filtered transaction dataframe. The sorting function adds a temporary sort column based on the specified sort field, ensuring that the sort is deterministic and handles edge cases (e.g., invalid timestamps or amounts). The limiting function simply takes the top N rows based on the specified limit. Both functions return new dataframes without mutating the input.
def _ensure_non_empty_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a defensive copy of the dataframe, preserving empty results safely."""
    return df.copy()


def _normalize_sort_columns(
    df: pd.DataFrame,
    sort_by: str,
) -> pd.DataFrame:
    """Prepare a dataframe with deterministic temporary sort columns."""
    sortable_df = _ensure_non_empty_dataframe(df)

    if sortable_df.empty:
        return sortable_df

    if sort_by == "timestamp":
        timestamp_series = pd.to_datetime(sortable_df["timestamp"], errors="coerce", utc=True)
        if timestamp_series.isna().any():
            raise TransactionLookupInputError(
                "Input dataframe contains invalid timestamp values that cannot be sorted safely."
            )
        sortable_df["_sort_value"] = timestamp_series
        return sortable_df

    if sort_by == "amount":
        normalized_amounts: list[Decimal] = []
        for raw_value in sortable_df["amount"].tolist():
            if pd.isna(raw_value):
                raise TransactionLookupInputError(
                    "Input dataframe contains null amount values."
                )
            try:
                normalized_amount = Decimal(str(raw_value)).quantize(DECIMAL_QUANTIZE_PLACES)
            except Exception as exc:  # pragma: no cover
                raise TransactionLookupInputError(
                    f"Input dataframe contains invalid amount value: {raw_value!r}."
                ) from exc
            normalized_amounts.append(normalized_amount)

        sortable_df["_sort_value"] = pd.Series(
            normalized_amounts,
            index=sortable_df.index,
            dtype="object",
        )
        return sortable_df

    sortable_df["_sort_value"] = sortable_df[sort_by].astype(str).str.strip().str.lower()
    return sortable_df


def sort_transaction_results(
    df: pd.DataFrame,
    *,
    sort_by: str,
    sort_descending: bool,
) -> pd.DataFrame:
    """Sort filtered transaction rows deterministically."""
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise TransactionLookupInputError(
            f"Unsupported sort_by '{sort_by}'. Allowed values: {sorted(ALLOWED_SORT_FIELDS)}."
        )

    sortable_df = _normalize_sort_columns(df, sort_by)

    if sortable_df.empty:
        return sortable_df

    sorted_df = sortable_df.sort_values(
        by=["_sort_value", "transaction_id"],
        ascending=[not sort_descending, True],
        kind="mergesort",
    )

    return sorted_df.drop(columns=["_sort_value"]).copy()


def limit_transaction_results(
    df: pd.DataFrame,
    *,
    limit: int,
) -> pd.DataFrame:
    """Limit sorted transaction rows deterministically."""
    if limit <= 0:
        raise TransactionLookupInputError(LIMIT_POSITIVE_ERROR)

    return df.head(limit).copy()
##BRICK 5: Implement normalization functions for the output transaction fields (string fields, amount field, timestamp field). These functions ensure that the final transaction records are constructed with clean, validated, and appropriately typed values. The main function to build a transaction record takes a dataframe row and applies these normalization functions to construct a typed TransactionRecord dataclass instance.
def _normalize_string_field(value: Any) -> str:
    """Normalize a required string-like output field."""
    if pd.isna(value):
        raise TransactionLookupInputError("Encountered null value in required string field.")

    normalized = str(value).strip()
    if not normalized:
        raise TransactionLookupInputError("Encountered blank value in required string field.")

    return normalized


def _normalize_amount_field(value: Any) -> Decimal:
    """Normalize a required amount field into a quantized Decimal."""
    if pd.isna(value):
        raise TransactionLookupInputError("Encountered null value in required amount field.")

    try:
        return Decimal(str(value)).quantize(DECIMAL_QUANTIZE_PLACES)
    except Exception as exc:  # pragma: no cover
        raise TransactionLookupInputError(
            f"Encountered invalid amount value in output row: {value!r}."
        ) from exc


def _normalize_timestamp_field(value: Any) -> str:
    """Normalize a required timestamp field into an ISO-like UTC string."""
    if pd.isna(value):
        raise TransactionLookupInputError("Encountered null value in required timestamp field.")

    timestamp = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(timestamp):
        raise TransactionLookupInputError(
            f"Encountered invalid timestamp value in output row: {value!r}."
        )

    return timestamp.isoformat()


def build_transaction_record(row: pd.Series) -> TransactionRecord:
    """Convert one filtered dataframe row into a typed transaction record."""
    return TransactionRecord(
        transaction_id=_normalize_string_field(row["transaction_id"]),
        account_id=_normalize_string_field(row["account_id"]),
        timestamp=_normalize_timestamp_field(row["timestamp"]),
        amount=_normalize_amount_field(row["amount"]),
        currency=_normalize_string_field(row["currency"]),
        direction=_normalize_string_field(row["direction"]),
        merchant=_normalize_string_field(row["merchant"]),
        category=_normalize_string_field(row["category"]),
        subcategory=_normalize_string_field(row["subcategory"]),
    )


def build_transaction_records(df: pd.DataFrame) -> tuple[TransactionRecord, ...]:
    """Convert a filtered dataframe into typed transaction records."""
    if df.empty:
        return ()

    records: list[TransactionRecord] = []
    for _, row in df.iterrows():
        records.append(build_transaction_record(row))

    return tuple(records)
##BRICK 6: Implement functions to build deterministic warnings based on the transaction lookup results and to construct an audit-safe view of the applied filters. The warning function checks for conditions such as no matching transactions or multiple currencies in the results, while the applied filters function creates a dictionary representation of the filters used in the lookup request, ensuring that all values are appropriately serialized for auditing purposes.
def build_lookup_warnings(records: tuple[TransactionRecord, ...]) -> tuple[str, ...]:
    """Build deterministic warnings for transaction lookup results."""
    warnings: list[str] = []

    if not records:
        warnings.append("No transactions matched the provided filters.")
        return tuple(warnings)

    currencies = {record.currency for record in records}
    if len(currencies) > 1:
        warnings.append(
            "Multiple currencies detected in lookup results. Values should not be combined implicitly."
        )

    return tuple(warnings)


def build_applied_filters(
    request: TransactionLookupRequest,
) -> dict[str, Any]:
    """Build an audit-safe view of the applied lookup filters."""
    return {
        "user_id": request.user_id,
        "transaction_ids": request.transaction_ids,
        "account_ids": request.account_ids,
        "merchants": request.merchants,
        "categories": request.categories,
        "direction": request.direction,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "min_amount": str(request.min_amount) if request.min_amount is not None else None,
        "max_amount": str(request.max_amount) if request.max_amount is not None else None,
        "limit": request.limit,
        "sort_by": request.sort_by,
        "sort_descending": request.sort_descending,
    }

##BRICK 7: Implement the main transaction lookup function that orchestrates the entire process. This function takes a processed transaction dataframe and a normalized transaction lookup request, validates the input, applies the filters, sorts and limits the results, builds the transaction records, generates any necessary warnings, and constructs the final TransactionLookupResult dataclass instance. It also includes logging for auditability and debugging purposes.
def lookup_transactions(
    df: pd.DataFrame,
    request: TransactionLookupRequest,
) -> TransactionLookupResult:
    """Run the deterministic transaction lookup tool on a processed transaction dataframe."""
    validate_required_columns(df)

    filtered_df = apply_transaction_lookup_filters(df, request)
    sorted_df = sort_transaction_results(
        filtered_df,
        sort_by=request.sort_by,
        sort_descending=request.sort_descending,
    )
    limited_df = limit_transaction_results(sorted_df, limit=request.limit)

    records = build_transaction_records(limited_df)
    warnings = build_lookup_warnings(records)
    applied_filters = build_applied_filters(request)

    logger.info(
        "Transaction lookup computed successfully.",
        extra={
            "rows_in": len(df),
            "rows_after_filters": len(filtered_df),
            "rows_after_limit": len(limited_df),
            "match_count": len(records),
            "sort_by": request.sort_by,
            "sort_descending": request.sort_descending,
        },
    )

    return TransactionLookupResult(
        records=records,
        match_count=len(records),
        applied_filters=applied_filters,
        warnings=warnings,
    )
##BRICK 8: Implement a serialization function to convert the TransactionLookupResult dataclass instance into a JSON-friendly dictionary format. This function ensures that all fields are appropriately serialized, such as converting Decimal amounts to strings and ensuring that any complex types are represented in a way that can be easily consumed by downstream systems or APIs.
def transaction_lookup_result_to_dict(
    result: TransactionLookupResult,
) -> dict[str, Any]:
    """Serialize a transaction lookup result into a JSON-friendly dictionary."""
    return {
        "records": [
            {
                "transaction_id": record.transaction_id,
                "account_id": record.account_id,
                "timestamp": record.timestamp,
                "amount": str(record.amount),
                "currency": record.currency,
                "direction": record.direction,
                "merchant": record.merchant,
                "category": record.category,
                "subcategory": record.subcategory,
            }
            for record in result.records
        ],
        "match_count": result.match_count,
        "applied_filters": dict(result.applied_filters),
        "warnings": list(result.warnings),
    }
