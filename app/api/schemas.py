# app/api/schemas.py
# 2026-04-02
"""Purpose: Define the request and response models shared by the Payjack API and frontend."""

from __future__ import annotations

##BRICK 1: Imports and shared response models
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    title: str
    snippet: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    artifact_version: str | None = None


class Refusal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    message: str


##BRICK 2: Chat request and response envelopes
class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    session_id: str | None = None
    client_request_id: str | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    session_id: str
    route: str
    answer: str
    tool_traces: list[ToolTrace] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    refusal: Refusal | None = None
    debug: dict[str, Any] = Field(default_factory=dict)

##BRICK 3: Direct tool invocation models
class ToolInvokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolInvokeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    tool: str
    arguments: dict[str, Any]
    payload: dict[str, Any]
    warnings: list[str]
    artifact_version: str | None
    latency_ms: float

print("API schemas for chat requests and responses have been defined.")
