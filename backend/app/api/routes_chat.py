from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.schemas import ChatRequest, ChatResponse
from app.errors import to_http_exception
from app.security.auth_context import AuthContext


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, payload: ChatRequest) -> ChatResponse:
    dependencies = request.app.state.dependencies
    auth_context = AuthContext.from_headers(request.headers)
    try:
        return dependencies.workflow_engine.handle_chat(
            payload,
            auth_context=auth_context,
        )
    except Exception as exc:  # pragma: no cover - exercised in integration tests
        raise to_http_exception(exc) from exc
