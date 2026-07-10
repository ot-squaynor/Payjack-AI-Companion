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
    """Formats the response from the orchestrator into a ChatResponse object that can be returned to the client.
    This function takes the raw components of the response, including the request ID, session ID,
    route, generated answer, tool traces, citations, refusal information, and any debug data, 
    and constructs a ChatResponse object that encapsulates all of this information in a structured format.
    The tool traces and citations are converted from their raw dictionary forms into lists of ToolTrace and
    Citation objects, respectively, while the refusal information is converted into a Refusal object if it is present. 
    The resulting ChatResponse object provides a clear and organized representation of the response that can be easily consumed 
    by the client application."""
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
