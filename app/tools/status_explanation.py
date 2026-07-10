from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class StatusExplanationRequest:
    user_id: str | None = None
    account_ids: tuple[str, ...] = ()
    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True, slots=True)
class StatusExplanationResult:
    counts_by_status: dict[str, int]
    warnings: tuple[str, ...] = field(default_factory=tuple)


def normalize_status_explanation_request(
    *,
    user_id: str | None = None,
    account_ids: Any = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> StatusExplanationRequest:
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

    return StatusExplanationRequest(
        user_id=user_id,
        account_ids=normalized_account_ids,
        start_date=start_date,
        end_date=end_date,
    )


def explain_statuses(
    df: pd.DataFrame,
    request: StatusExplanationRequest,
) -> StatusExplanationResult:
    if "status" not in df.columns:
        return StatusExplanationResult(
            counts_by_status={},
            warnings=("The processed transactions dataset does not yet include a status column.",),
        )

    working_df = df.copy()
    if request.account_ids:
        working_df = working_df[working_df["account_id"].astype(str).isin(request.account_ids)].copy()

    if request.start_date or request.end_date:
        timestamps = pd.to_datetime(working_df["timestamp"], errors="coerce", utc=True)
        working_df = working_df.assign(timestamp=timestamps)
        if request.start_date:
            working_df = working_df[working_df["timestamp"] >= pd.Timestamp(request.start_date, tz="UTC")]
        if request.end_date:
            working_df = working_df[working_df["timestamp"] <= pd.Timestamp(request.end_date, tz="UTC")]

    counts_by_status = (
        working_df["status"]
        .fillna("unknown")
        .astype(str)
        .str.lower()
        .value_counts()
        .to_dict()
    )

    return StatusExplanationResult(
        counts_by_status={str(key): int(value) for key, value in counts_by_status.items()}
    )


def status_explanation_result_to_dict(result: StatusExplanationResult) -> dict[str, Any]:
    return {
        "counts_by_status": dict(result.counts_by_status),
        "warnings": list(result.warnings),
    }
