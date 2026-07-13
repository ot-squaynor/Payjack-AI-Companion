# app/api/routes_chat_sessions.py
"""Purpose: Expose persisted chat session/message endpoints and translate runtime errors into HTTP responses."""

from __future__ import annotations

##BRICK 1: Imports and router definition
from fastapi import APIRouter, Query, Request

from app.api.schemas_chat_sessions import (
    MessageListResponse,
    MessageResponse,
    SessionCreateRequest,
    SessionListResponse,
    SessionResponse,
    SessionUpdateRequest,
)
from app.chat_history.contracts import ChatMessageRecord, ChatSessionRecord
from app.chat_history.store import ChatHistoryError, ChatHistorySessionNotFoundError
from app.errors import NotFoundError, ResourceNotReadyError, ValidationError, to_http_exception
from app.security.audit_logging import log_audit_event
from app.security.auth_context import AuthContext


router = APIRouter(tags=["chat_sessions"])


##BRICK 2: Record -> response conversion
def _session_response(record: ChatSessionRecord) -> SessionResponse:
    return SessionResponse(
        session_id=record.session_id,
        title=record.title,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        message_count=record.message_count,
        last_message_preview=record.last_message_preview,
        last_message_role=record.last_message_role,
    )


def _message_response(record: ChatMessageRecord) -> MessageResponse:
    return MessageResponse(
        message_id=record.message_id,
        role=record.role,
        content=record.content,
        created_at=record.created_at,
        request_id=record.request_id,
        route=record.route,
        tool_traces=record.tool_traces,
        citations=record.citations,
        refusal=record.refusal,
        debug=record.debug,
    )


def _store(request: Request):
    dependencies = request.app.state.dependencies
    if dependencies.chat_history_store is None:
        raise ResourceNotReadyError("Chat history persistence is not configured for this environment.")
    return dependencies.chat_history_store


##BRICK 3: Session routes
@router.post("/chat/sessions")
async def create_session(request: Request, payload: SessionCreateRequest) -> SessionResponse:
    auth_context = AuthContext.from_headers(request.headers)
    try:
        store = _store(request)
        record = store.create_session(auth_context=auth_context, title=payload.title)
    except ChatHistoryError as exc:
        raise to_http_exception(ResourceNotReadyError(str(exc))) from exc
    except Exception as exc:
        raise to_http_exception(exc) from exc

    log_audit_event(
        event_type="chat_session_created",
        request_id=record.session_id,
        auth_context=auth_context,
        payload={"session_id": record.session_id},
    )
    return _session_response(record)


@router.get("/chat/sessions")
async def list_sessions(
    request: Request,
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> SessionListResponse:
    auth_context = AuthContext.from_headers(request.headers)
    try:
        store = _store(request)
        records, next_cursor = store.list_sessions(
            auth_context=auth_context,
            include_archived=include_archived,
            limit=limit,
            cursor=cursor,
        )
    except ChatHistoryError as exc:
        raise to_http_exception(ResourceNotReadyError(str(exc))) from exc
    except Exception as exc:
        raise to_http_exception(exc) from exc

    return SessionListResponse(
        sessions=[_session_response(record) for record in records],
        next_cursor=next_cursor,
    )


@router.get("/chat/sessions/{session_id}")
async def get_session(request: Request, session_id: str) -> SessionResponse:
    auth_context = AuthContext.from_headers(request.headers)
    try:
        store = _store(request)
        record = store.get_session(session_id=session_id, auth_context=auth_context)
    except ChatHistoryError as exc:
        raise to_http_exception(ResourceNotReadyError(str(exc))) from exc
    except Exception as exc:
        raise to_http_exception(exc) from exc

    if record is None:
        raise to_http_exception(NotFoundError(f"Session {session_id!r} was not found."))
    return _session_response(record)


@router.patch("/chat/sessions/{session_id}")
async def update_session(
    request: Request, session_id: str, payload: SessionUpdateRequest
) -> SessionResponse:
    if payload.title is None and payload.status is None:
        raise to_http_exception(
            ValidationError("At least one of 'title' or 'status' must be provided.")
        )
    if payload.status is not None and payload.status not in {"active", "archived"}:
        raise to_http_exception(
            ValidationError(f"Unsupported status: {payload.status!r}. Expected 'active' or 'archived'.")
        )

    auth_context = AuthContext.from_headers(request.headers)
    try:
        store = _store(request)
        record: ChatSessionRecord | None = None
        if payload.title is not None:
            record = store.rename_session(
                session_id=session_id, auth_context=auth_context, title=payload.title
            )
        if payload.status is not None:
            record = store.set_session_status(
                session_id=session_id,
                auth_context=auth_context,
                status=payload.status,
                archive_ttl_days=request.app.state.dependencies.settings.chat_history_archive_ttl_days,
            )
    except ChatHistorySessionNotFoundError as exc:
        raise to_http_exception(NotFoundError(str(exc))) from exc
    except ChatHistoryError as exc:
        raise to_http_exception(ResourceNotReadyError(str(exc))) from exc
    except Exception as exc:
        raise to_http_exception(exc) from exc

    assert record is not None  # one of the branches above always runs

    if payload.title is not None:
        log_audit_event(
            event_type="chat_session_renamed",
            request_id=session_id,
            auth_context=auth_context,
            payload={"session_id": session_id, "title": payload.title},
        )
    if payload.status is not None:
        event_type = "chat_session_archived" if payload.status == "archived" else "chat_session_reactivated"
        log_audit_event(
            event_type=event_type,
            request_id=session_id,
            auth_context=auth_context,
            payload={"session_id": session_id, "status": payload.status},
        )

    return _session_response(record)


@router.delete("/chat/sessions/{session_id}")
async def delete_session(request: Request, session_id: str) -> dict[str, object]:
    auth_context = AuthContext.from_headers(request.headers)
    try:
        store = _store(request)
        store.delete_session(session_id=session_id, auth_context=auth_context)
    except ChatHistorySessionNotFoundError as exc:
        raise to_http_exception(NotFoundError(str(exc))) from exc
    except ChatHistoryError as exc:
        raise to_http_exception(ResourceNotReadyError(str(exc))) from exc
    except Exception as exc:
        raise to_http_exception(exc) from exc

    log_audit_event(
        event_type="chat_session_deleted",
        request_id=session_id,
        auth_context=auth_context,
        payload={"session_id": session_id},
    )
    return {"session_id": session_id, "deleted": True}


##BRICK 4: Message routes
@router.get("/chat/sessions/{session_id}/messages")
async def list_messages(
    request: Request,
    session_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    cursor: str | None = Query(default=None),
) -> MessageListResponse:
    auth_context = AuthContext.from_headers(request.headers)
    try:
        store = _store(request)
        records, next_cursor = store.list_messages(
            session_id=session_id,
            auth_context=auth_context,
            limit=limit,
            cursor=cursor,
        )
    except ChatHistorySessionNotFoundError as exc:
        raise to_http_exception(NotFoundError(str(exc))) from exc
    except ChatHistoryError as exc:
        raise to_http_exception(ResourceNotReadyError(str(exc))) from exc
    except Exception as exc:
        raise to_http_exception(exc) from exc

    return MessageListResponse(
        session_id=session_id,
        messages=[_message_response(record) for record in records],
        next_cursor=next_cursor,
    )
