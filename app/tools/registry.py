# app/tools/registry.py
# 2026-03-02
"""Purpose: Define the ToolRegistry for managing and invoking data processing tools."""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any

from app.repository.processed_store import ProcessedStore
from app.security.access_control import resolve_account_scope
from app.security.auth_context import AuthContext
from app.tools.balances import balance_result_to_dict, lookup_balances, normalize_balance_request
from app.tools.fee_breakdown import (
    breakdown_fees,
    fee_breakdown_result_to_dict,
    normalize_fee_breakdown_request,
)
from app.tools.recurring_detection import (
    detect_recurring_payments,
    normalize_recurring_detection_request,
    recurring_detection_result_to_dict,
)
from app.tools.spend_summary import (
    normalize_spend_summary_request,
    spend_summary_result_to_dict,
    summarize_spend,
)
from app.tools.status_explanation import (
    explain_statuses,
    normalize_status_explanation_request,
    status_explanation_result_to_dict,
)
from app.tools.transaction_lookup import (
    lookup_transactions,
    normalize_transaction_lookup_request,
    transaction_lookup_result_to_dict,
)


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResult:
    name: str
    arguments: dict[str, Any]
    payload: dict[str, Any]
    warnings: tuple[str, ...] = ()
    artifact_version: str | None = None
    latency_ms: float = 0.0


class ToolRegistry:
    def __init__(self, *, store: ProcessedStore) -> None:
        self.store = store

    def invoke(
        self,
        invocation: ToolInvocation,
        *,
        auth_context: AuthContext,
    ) -> ToolResult:
        manifest = self.store.get_manifest()
        started_at = time.perf_counter()
        scoped_arguments = dict(invocation.arguments)
        scoped_arguments["account_ids"] = resolve_account_scope(
            requested_account_ids=tuple(scoped_arguments.get("account_ids", ()) or ()),
            auth_context=auth_context,
        )

        if invocation.name == "transaction_lookup":
            result = lookup_transactions(
                self.store.get_transactions(),
                normalize_transaction_lookup_request(
                    user_id=auth_context.user_id,
                    **scoped_arguments,
                ),
            )
            payload = transaction_lookup_result_to_dict(result)
            warnings = tuple(result.warnings)
        elif invocation.name == "spend_summary":
            result = summarize_spend(
                self.store.get_transactions(),
                normalize_spend_summary_request(
                    user_id=auth_context.user_id,
                    **scoped_arguments,
                ),
            )
            payload = spend_summary_result_to_dict(result)
            warnings = tuple(result.warnings)
        elif invocation.name == "recurring_detection":
            result = detect_recurring_payments(
                self.store.get_transactions(),
                normalize_recurring_detection_request(
                    user_id=auth_context.user_id,
                    **scoped_arguments,
                ),
            )
            payload = recurring_detection_result_to_dict(result)
            warnings = tuple(result.warnings)
        elif invocation.name == "balances":
            result = lookup_balances(
                self.store.get_accounts(),
                normalize_balance_request(
                    user_id=auth_context.user_id,
                    **scoped_arguments,
                ),
            )
            payload = balance_result_to_dict(result)
            warnings = tuple(result.warnings)
        elif invocation.name == "status_explanation":
            result = explain_statuses(
                self.store.get_transactions(),
                normalize_status_explanation_request(
                    user_id=auth_context.user_id,
                    **scoped_arguments,
                ),
            )
            payload = status_explanation_result_to_dict(result)
            warnings = tuple(result.warnings)
        elif invocation.name == "fee_breakdown":
            result = breakdown_fees(
                self.store.get_transactions(),
                normalize_fee_breakdown_request(
                    user_id=auth_context.user_id,
                    **scoped_arguments,
                ),
            )
            payload = fee_breakdown_result_to_dict(result)
            warnings = tuple(result.warnings)
        else:
            raise ValueError(f"Unsupported tool invocation: {invocation.name}")

        return ToolResult(
            name=invocation.name,
            arguments=scoped_arguments,
            payload=payload,
            warnings=warnings,
            artifact_version=manifest.dataset_version,
            latency_ms=round((time.perf_counter() - started_at) * 1000, 3),
        )
