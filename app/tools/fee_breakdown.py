from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pandas as pd


FEE_TERMS = ("fee", "charge", "levy", "commission", "service charge")
REQUIRED_COLUMNS = frozenset(
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


class FeeBreakdownError(Exception):
    """Base exception for deterministic fee breakdown failures."""


class FeeBreakdownInputError(FeeBreakdownError):
    """Raised when fee breakdown inputs are invalid."""


@dataclass(frozen=True, slots=True)
class FeeBreakdownRequest:
    user_id: str | None = None
    account_ids: tuple[str, ...] = ()
    transaction_ids: tuple[str, ...] = ()
    start_date: str | None = None
    end_date: str | None = None
    limit: int = 10


@dataclass(frozen=True, slots=True)
class FeeRecord:
    transaction_id: str
    account_id: str
    timestamp: str
    amount: Decimal
    currency: str
    direction: str
    merchant: str
    category: str
    subcategory: str
    matched_reason: str


@dataclass(frozen=True, slots=True)
class FeeBreakdownResult:
    records: tuple[FeeRecord, ...]
    total_amount: Decimal
    transaction_count: int
    currency_breakdown: dict[str, Decimal]
    applied_filters: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


def _normalize_string_tuple(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        candidates = [values]
    else:
        candidates = list(values)
    return tuple(str(value).strip() for value in candidates if str(value).strip())


def normalize_fee_breakdown_request(
    *,
    user_id: str | None = None,
    account_ids: Any = None,
    transaction_ids: Any = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 10,
) -> FeeBreakdownRequest:
    if not isinstance(limit, int) or limit <= 0:
        raise FeeBreakdownInputError("limit must be a positive integer.")
    if start_date and end_date and start_date > end_date:
        raise FeeBreakdownInputError("start_date must be less than or equal to end_date.")
    return FeeBreakdownRequest(
        user_id=user_id.strip() if isinstance(user_id, str) and user_id.strip() else None,
        account_ids=_normalize_string_tuple(account_ids),
        transaction_ids=_normalize_string_tuple(transaction_ids),
        start_date=start_date.strip() if isinstance(start_date, str) and start_date.strip() else None,
        end_date=end_date.strip() if isinstance(end_date, str) and end_date.strip() else None,
        limit=min(limit, 100),
    )


def validate_required_columns(df: pd.DataFrame) -> None:
    missing_columns = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing_columns:
        raise FeeBreakdownInputError(f"Input dataframe is missing required columns: {missing_columns}.")


def _fee_match_reason(row: pd.Series) -> str | None:
    fields = {
        "category": str(row.get("category", "")).lower(),
        "subcategory": str(row.get("subcategory", "")).lower(),
        "merchant": str(row.get("merchant", "")).lower(),
    }
    for field_name, value in fields.items():
        if any(term in value for term in FEE_TERMS):
            return f"{field_name}_matched_fee_term"
    return None


def _apply_filters(df: pd.DataFrame, request: FeeBreakdownRequest) -> pd.DataFrame:
    working_df = df.copy()
    if request.account_ids:
        working_df = working_df[working_df["account_id"].astype(str).isin(request.account_ids)].copy()
    if request.transaction_ids:
        working_df = working_df[working_df["transaction_id"].astype(str).isin(request.transaction_ids)].copy()
    if request.start_date or request.end_date:
        timestamps = pd.to_datetime(working_df["timestamp"], errors="coerce", utc=True)
        working_df = working_df.assign(timestamp=timestamps)
        if request.start_date:
            working_df = working_df[working_df["timestamp"] >= pd.Timestamp(request.start_date, tz="UTC")]
        if request.end_date:
            working_df = working_df[working_df["timestamp"] <= pd.Timestamp(request.end_date, tz="UTC")]
    return working_df


def _build_record(row: pd.Series, *, matched_reason: str) -> FeeRecord:
    timestamp = pd.to_datetime(row["timestamp"], errors="coerce", utc=True)
    if pd.isna(timestamp):
        raise FeeBreakdownInputError("Encountered invalid timestamp in fee record.")
    return FeeRecord(
        transaction_id=str(row["transaction_id"]).strip(),
        account_id=str(row["account_id"]).strip(),
        timestamp=timestamp.isoformat(),
        amount=Decimal(str(row["amount"])).quantize(Decimal("0.01")),
        currency=str(row["currency"]).strip(),
        direction=str(row["direction"]).strip(),
        merchant=str(row["merchant"]).strip(),
        category=str(row["category"]).strip(),
        subcategory=str(row["subcategory"]).strip(),
        matched_reason=matched_reason,
    )


def breakdown_fees(df: pd.DataFrame, request: FeeBreakdownRequest) -> FeeBreakdownResult:
    validate_required_columns(df)
    filtered_df = _apply_filters(df, request)

    matched_rows: list[FeeRecord] = []
    for _, row in filtered_df.iterrows():
        reason = _fee_match_reason(row)
        if reason is not None:
            matched_rows.append(_build_record(row, matched_reason=reason))

    matched_rows.sort(key=lambda row: row.timestamp, reverse=True)
    records = tuple(matched_rows[: request.limit])
    currency_breakdown: dict[str, Decimal] = {}
    for record in records:
        currency_breakdown[record.currency] = currency_breakdown.get(record.currency, Decimal("0.00")) + record.amount
    total_amount = sum(currency_breakdown.values(), Decimal("0.00")).quantize(Decimal("0.01"))

    warnings: list[str] = []
    if not records:
        warnings.append("No fee-like transactions matched the provided filters.")
    if len(currency_breakdown) > 1:
        warnings.append("Multiple currencies detected in fee results. Values should not be combined implicitly.")

    return FeeBreakdownResult(
        records=records,
        total_amount=total_amount,
        transaction_count=len(records),
        currency_breakdown=currency_breakdown,
        applied_filters={
            "user_id": request.user_id,
            "account_ids": request.account_ids,
            "transaction_ids": request.transaction_ids,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "limit": request.limit,
        },
        warnings=tuple(warnings),
    )


def fee_breakdown_result_to_dict(result: FeeBreakdownResult) -> dict[str, Any]:
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
                "matched_reason": record.matched_reason,
            }
            for record in result.records
        ],
        "total_amount": str(result.total_amount),
        "transaction_count": result.transaction_count,
        "currency_breakdown": {
            currency: str(amount)
            for currency, amount in result.currency_breakdown.items()
        },
        "applied_filters": dict(result.applied_filters),
        "warnings": list(result.warnings),
    }
