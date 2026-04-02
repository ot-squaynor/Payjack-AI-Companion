from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class BalanceRequest:
    user_id: str | None = None
    account_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BalanceRecord:
    account_id: str
    account_name: str | None
    currency: str | None
    current_balance: Decimal | None
    available_balance: Decimal | None


@dataclass(frozen=True, slots=True)
class BalanceResult:
    records: tuple[BalanceRecord, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)


def normalize_balance_request(
    *,
    user_id: str | None = None,
    account_ids: Any = None,
) -> BalanceRequest:
    if account_ids is None:
        normalized_account_ids: tuple[str, ...] = ()
    elif isinstance(account_ids, str):
        normalized_account_ids = (account_ids.strip(),) if account_ids.strip() else ()
    else:
        normalized_account_ids = tuple(
            str(account_id).strip()
            for account_id in account_ids
            if str(account_id).strip()
        )

    return BalanceRequest(user_id=user_id, account_ids=normalized_account_ids)


def lookup_balances(df: pd.DataFrame, request: BalanceRequest) -> BalanceResult:
    working_df = df.copy()
    warnings: list[str] = []

    if request.account_ids:
        working_df = working_df[working_df["account_id"].astype(str).isin(request.account_ids)].copy()

    if working_df.empty:
        warnings.append("No accounts matched the provided balance filters.")
        return BalanceResult(records=(), warnings=tuple(warnings))

    records: list[BalanceRecord] = []
    for _, row in working_df.iterrows():
        current_balance = row.get("current_balance", row.get("balance"))
        available_balance = row.get("available_balance", current_balance)
        if current_balance is not None and not pd.isna(current_balance):
            current_balance = Decimal(str(current_balance)).quantize(Decimal("0.01"))
        else:
            current_balance = None
            warnings.append("Some accounts do not yet have a current_balance field in the processed dataset.")

        if available_balance is not None and not pd.isna(available_balance):
            available_balance = Decimal(str(available_balance)).quantize(Decimal("0.01"))
        else:
            available_balance = None

        records.append(
            BalanceRecord(
                account_id=str(row.get("account_id", "")).strip(),
                account_name=str(row.get("account_name", "")).strip() or None,
                currency=str(row.get("currency", "")).strip() or None,
                current_balance=current_balance,
                available_balance=available_balance,
            )
        )

    deduped_warnings = tuple(dict.fromkeys(warnings))
    return BalanceResult(records=tuple(records), warnings=deduped_warnings)


def balance_result_to_dict(result: BalanceResult) -> dict[str, Any]:
    return {
        "records": [
            {
                "account_id": record.account_id,
                "account_name": record.account_name,
                "currency": record.currency,
                "current_balance": None if record.current_balance is None else str(record.current_balance),
                "available_balance": None if record.available_balance is None else str(record.available_balance),
            }
            for record in result.records
        ],
        "warnings": list(result.warnings),
    }
