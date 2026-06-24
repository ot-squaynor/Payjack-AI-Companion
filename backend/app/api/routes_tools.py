# app/api/routes_tools.py
# 2026-06-24
"""Purpose: Expose a direct tool-invocation endpoint, bypassing the LLM orchestrator."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from app.api.schemas import ToolInvokeRequest, ToolInvokeResponse
from app.errors import ValidationError, to_http_exception
from app.security.auth_context import AuthContext
from app.tools.registry import ToolInvocation

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

router = APIRouter(tags=["tools"])


@router.post("/invoke", response_model=ToolInvokeResponse)
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
    invocation = ToolInvocation(name=payload.tool, arguments=payload.arguments)

    try:
        result = dependencies.tool_registry.invoke(invocation, auth_context=auth_context)
    except Exception as exc:
        raise to_http_exception(exc) from exc

    return ToolInvokeResponse(
        request_id=str(uuid.uuid4()),
        tool=result.name,
        arguments=result.arguments,
        payload=result.payload,
        warnings=list(result.warnings),
        artifact_version=result.artifact_version,
        latency_ms=result.latency_ms,
    )
