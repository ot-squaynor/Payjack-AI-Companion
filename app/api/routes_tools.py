# app/api/routes_tools.py
# 2026-06-24
"""Purpose: Expose a direct tool-invocation endpoint, bypassing the LLM orchestrator."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.api.schemas import ToolInvokeRequest, ToolInvokeResponse
from app.errors import ValidationError, to_http_exception
from app.repository.processed_store import ProcessedStoreError
from app.security.auth_context import AuthContext
from app.tools.fee_breakdown import FeeBreakdownInputError
from app.tools.recurring_detection import RecurringDetectionInputError
from app.tools.registry import ToolInvocation
from app.tools.spend_summary import SpendSummaryInputError
from app.tools.transaction_lookup import TransactionLookupInputError

ALLOWED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "transaction_lookup",
        "spend_summary",
        "recurring_detection",
        "balances",
        "status_explanation",
        "fee_breakdown",
    }
)

_TOOL_INPUT_ERRORS = (
    TransactionLookupInputError,
    SpendSummaryInputError,
    RecurringDetectionInputError,
    FeeBreakdownInputError,
)

_DATE_FIELD_MAP = {
    "date_from": "start_date",
    "date_to": "end_date",
}

_TRANSACTION_LOOKUP_FIELD_MAP = {
    "amount_min": "min_amount",
    "amount_max": "max_amount",
}

_RECURRING_DETECTION_FIELD_MAP = {
    "cadence": "cadences",
    "confidence": "confidences",
}


def _validated_date(value: Any, field: str) -> str:
    # Raises app ValidationError (AppError → 422) on bad format.
    try:
        datetime.strptime(str(value), "%Y-%m-%d")
        return str(value)
    except (ValueError, TypeError):
        raise ValidationError(
            f"Invalid date for '{field}': expected YYYY-MM-DD, got {value!r}"
        )


def _apply_date_aliases(args: dict[str, Any]) -> None:
    for source, target in _DATE_FIELD_MAP.items():
        if source in args:
            args[target] = _validated_date(args.pop(source), source)


def _apply_transaction_lookup_aliases(args: dict[str, Any]) -> None:
    for source, target in _TRANSACTION_LOOKUP_FIELD_MAP.items():
        if source in args:
            args[target] = args.pop(source)


def _apply_recurring_detection_aliases(args: dict[str, Any]) -> None:
    for source, target in _RECURRING_DETECTION_FIELD_MAP.items():
        value = args.pop(source, None)
        if value:
            args[target] = [value]


def _map_ui_args(tool: str, raw: dict[str, Any]) -> dict[str, Any]:
    # Translate UI argument names to internal normalizer argument names.
    # Unknown keys pass through unchanged so callers using the internal schema
    # (e.g. start_date/end_date) continue to work without modification.
    args = dict(raw)

    _apply_date_aliases(args)

    if tool == "transaction_lookup":
        _apply_transaction_lookup_aliases(args)

    if tool == "recurring_detection":
        _apply_recurring_detection_aliases(args)

    return args


router = APIRouter(tags=["tools"])


@router.post(
    "/invoke",
    responses={
        422: {
            "description": "Tool arguments failed validation.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "validation_error",
                            "message": "Invalid tool argument.",
                        }
                    }
                }
            },
        },
        503: {
            "description": "Required processed data artifact is unavailable.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "missing_artifact",
                            "message": "Processed artifact is unavailable.",
                        }
                    }
                }
            },
        },
    },
)
async def invoke_tool(request: Request, payload: ToolInvokeRequest) -> ToolInvokeResponse:
    if payload.tool not in ALLOWED_TOOL_NAMES:
        raise to_http_exception(
            ValidationError(
                f"Unknown tool: {payload.tool!r}. "
                f"Allowed tools: {sorted(ALLOWED_TOOL_NAMES)}"
            )
        )

    dependencies = request.app.state.dependencies
    auth_context = AuthContext.from_headers(request.headers)

    try:
        mapped_args = _map_ui_args(payload.tool, payload.arguments)
        invocation = ToolInvocation(name=payload.tool, arguments=mapped_args)
        result = dependencies.tool_registry.invoke(invocation, auth_context=auth_context)
    except ProcessedStoreError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "missing_artifact", "message": str(exc)},
        ) from exc
    except _TOOL_INPUT_ERRORS as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "validation_error", "message": str(exc)},
        ) from exc
    except Exception as exc:
        raise to_http_exception(exc) from exc  # handles AppError subclasses

    return ToolInvokeResponse(
        request_id=str(uuid.uuid4()),
        tool=result.name,
        arguments=result.arguments,
        payload=result.payload,
        warnings=list(result.warnings),
        artifact_version=result.artifact_version,
        latency_ms=result.latency_ms,
    )
