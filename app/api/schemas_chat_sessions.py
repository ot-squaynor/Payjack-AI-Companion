# app/api/schemas_chat_sessions.py
"""Purpose: Define the request and response models for the persisted chat sessions API."""

from __future__ import annotations

##BRICK 1: Imports
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas import Citation, Refusal, ToolTrace


##BRICK 2: Session request/response envelopes
class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None


class SessionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    status: str | None = None


class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    message_count: int
    last_message_preview: str | None = None
    last_message_role: str | None = None


class SessionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sessions: list[SessionResponse] = Field(default_factory=list)
    next_cursor: str | None = None


##BRICK 3: Message response envelopes
class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    role: str
    content: str
    created_at: str
    request_id: str | None = None
    route: str | None = None
    tool_traces: list[ToolTrace] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    refusal: Refusal | None = None
    debug: dict[str, Any] = Field(default_factory=dict)


class MessageListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    messages: list[MessageResponse] = Field(default_factory=list)
    next_cursor: str | None = None
