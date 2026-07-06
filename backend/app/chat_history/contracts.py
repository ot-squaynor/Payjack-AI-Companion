# app/chat_history/contracts.py
"""Purpose: Define the durable record shapes for persisted chat sessions and messages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ChatSessionRecord:
    session_id: str
    tenant_id: str
    user_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    message_count: int
    last_message_preview: str | None = None
    last_message_role: str | None = None
    archived_at: str | None = None


@dataclass(frozen=True, slots=True)
class ChatMessageRecord:
    session_id: str
    message_id: str
    role: str
    content: str
    created_at: str
    request_id: str | None = None
    route: str | None = None
    tool_traces: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    refusal: dict[str, Any] | None = None
    debug: dict[str, Any] = field(default_factory=dict)
