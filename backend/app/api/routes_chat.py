# app/api/routes_chat.py
# 2026-04-02
"""Purpose: Expose the Payjack chat endpoint and translate runtime errors into HTTP responses."""

from __future__ import annotations

##BRICK 1: Imports and router definition
from fastapi import APIRouter, Request

from app.api.schemas import ChatRequest, ChatResponse
from app.errors import to_http_exception
from app.security.auth_context import AuthContext


router = APIRouter(tags=["chat"])


##BRICK 2: Chat route
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
