from __future__ import annotations

from typing import Any

from app.api.schemas import ChatResponse, Citation, Refusal, ToolTrace


def format_chat_response(
    *,
    request_id: str,
    session_id: str,
    route: str,
    answer: str,
    tool_traces: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    refusal: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
) -> ChatResponse:
    return ChatResponse(
        request_id=request_id,
        session_id=session_id,
        route=route,
        answer=answer,
        tool_traces=[ToolTrace(**trace) for trace in tool_traces],
        citations=[Citation(**citation) for citation in citations],
        refusal=Refusal(**refusal) if refusal else None,
        debug=debug or {},
    )
