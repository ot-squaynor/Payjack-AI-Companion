# app/chat_history/store.py
"""Purpose: Persist chat sessions and messages in DynamoDB behind a small repository interface."""

from __future__ import annotations

##BRICK 1: Imports, contracts, and store error types
import base64
from datetime import datetime, timezone
from decimal import Decimal
import json
from typing import Any
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.chat_history.contracts import ChatMessageRecord, ChatSessionRecord
from app.security.auth_context import AuthContext


DEFAULT_SESSION_TITLE = "New conversation"
TITLE_MAX_CHARS = 60
TOOL_ECHO_PREFIX = "📊"
_BATCH_DELETE_CHUNK_SIZE = 25


class ChatHistoryError(RuntimeError):
    """Raised when chat history cannot be read or written safely."""


class ChatHistorySessionNotFoundError(ChatHistoryError):
    """Raised when a session does not exist or does not belong to the caller."""


##BRICK 2: Small pure helpers
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _owner_key(auth_context: AuthContext) -> str:
    return f"{auth_context.tenant_id}#{auth_context.user_id}"


def derive_session_title(first_user_message: str) -> str:
    """Port of the frontend's deriveTitle: truncate the first user message to 60 chars."""

    text = first_user_message.strip()
    if not text or text.startswith(TOOL_ECHO_PREFIX):
        return DEFAULT_SESSION_TITLE
    if len(text) > TITLE_MAX_CHARS:
        return text[:TITLE_MAX_CHARS] + "…"
    return text


def _encode_cursor(last_evaluated_key: dict[str, Any] | None) -> str | None:
    if not last_evaluated_key:
        return None
    payload = json.dumps(last_evaluated_key, sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decode_cursor(cursor: str) -> dict[str, Any]:
    payload = base64.urlsafe_b64decode(cursor.encode("ascii"))
    return json.loads(payload.decode("utf-8"))


def _to_dynamodb_safe(value: Any) -> Any:
    """Recursively convert floats to Decimal, as DynamoDB's boto3 resource API requires."""

    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _to_dynamodb_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_dynamodb_safe(item) for item in value]
    return value


def _from_dynamodb_safe(value: Any) -> Any:
    """Recursively convert DynamoDB Decimal values back to int/float for JSON responses."""

    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {key: _from_dynamodb_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_from_dynamodb_safe(item) for item in value]
    return value


##BRICK 3: ChatHistoryStore
class ChatHistoryStore:
    def __init__(
        self,
        *,
        sessions_table_name: str,
        messages_table_name: str,
        aws_region: str,
        dynamodb_resource: Any | None = None,
    ) -> None:
        self.sessions_table_name = sessions_table_name
        self.messages_table_name = messages_table_name
        self.aws_region = aws_region
        self._dynamodb_resource = dynamodb_resource

    @property
    def _dynamodb(self) -> Any:
        if self._dynamodb_resource is None:
            self._dynamodb_resource = boto3.resource("dynamodb", region_name=self.aws_region)
        return self._dynamodb_resource

    @property
    def _sessions_table(self) -> Any:
        return self._dynamodb.Table(self.sessions_table_name)

    @property
    def _messages_table(self) -> Any:
        return self._dynamodb.Table(self.messages_table_name)

    ##BRICK 4: Item <-> record conversion
    def _session_from_item(self, item: dict[str, Any]) -> ChatSessionRecord:
        return ChatSessionRecord(
            session_id=item["session_id"],
            tenant_id=item["tenant_id"],
            user_id=item["user_id"],
            title=item["title"],
            status=item["status"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
            message_count=int(item.get("message_count", 0)),
            last_message_preview=item.get("last_message_preview"),
            last_message_role=item.get("last_message_role"),
            archived_at=item.get("archived_at"),
        )

    def _message_from_item(self, item: dict[str, Any]) -> ChatMessageRecord:
        return ChatMessageRecord(
            session_id=item["session_id"],
            message_id=item["message_id"],
            role=item["role"],
            content=item["content"],
            created_at=item["created_at"],
            request_id=item.get("request_id"),
            route=item.get("route"),
            tool_traces=_from_dynamodb_safe(list(item.get("tool_traces") or [])),
            citations=_from_dynamodb_safe(list(item.get("citations") or [])),
            refusal=_from_dynamodb_safe(item.get("refusal")),
            debug=_from_dynamodb_safe(dict(item.get("debug") or {})),
        )

    def _get_session_item(self, session_id: str) -> dict[str, Any] | None:
        try:
            response = self._sessions_table.get_item(Key={"session_id": session_id})
        except (BotoCoreError, ClientError) as exc:
            raise ChatHistoryError(f"Failed to read session {session_id!r}: {exc}") from exc
        return response.get("Item")

    def _authorized_session_item(
        self,
        *,
        session_id: str,
        auth_context: AuthContext,
    ) -> dict[str, Any] | None:
        item = self._get_session_item(session_id)
        if item is None or item.get("owner_key") != _owner_key(auth_context):
            return None
        return item

    def _require_authorized_session_item(
        self,
        *,
        session_id: str,
        auth_context: AuthContext,
    ) -> dict[str, Any]:
        item = self._authorized_session_item(session_id=session_id, auth_context=auth_context)
        if item is None:
            raise ChatHistorySessionNotFoundError(f"Session {session_id!r} was not found.")
        return item

    ##BRICK 5: Session operations
    def create_session(
        self,
        *,
        auth_context: AuthContext,
        session_id: str | None = None,
        title: str | None = None,
    ) -> ChatSessionRecord:
        now = _now_iso()
        resolved_session_id = session_id or f"session-{uuid.uuid4().hex[:12]}"
        item = {
            "session_id": resolved_session_id,
            "owner_key": _owner_key(auth_context),
            "tenant_id": auth_context.tenant_id,
            "user_id": auth_context.user_id,
            "title": title or DEFAULT_SESSION_TITLE,
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
        }
        try:
            self._sessions_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(session_id)",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                existing = self._get_session_item(resolved_session_id)
                if existing is not None:
                    return self._session_from_item(existing)
            raise ChatHistoryError(f"Failed to create session: {exc}") from exc
        except BotoCoreError as exc:
            raise ChatHistoryError(f"Failed to create session: {exc}") from exc
        return self._session_from_item(item)

    def get_or_create_session(
        self,
        *,
        session_id: str,
        auth_context: AuthContext,
    ) -> ChatSessionRecord:
        existing = self._get_session_item(session_id)
        if existing is not None:
            return self._session_from_item(existing)
        return self.create_session(auth_context=auth_context, session_id=session_id)

    def get_session(
        self,
        *,
        session_id: str,
        auth_context: AuthContext,
    ) -> ChatSessionRecord | None:
        item = self._authorized_session_item(session_id=session_id, auth_context=auth_context)
        return self._session_from_item(item) if item is not None else None

    def list_sessions(
        self,
        *,
        auth_context: AuthContext,
        include_archived: bool = False,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[ChatSessionRecord], str | None]:
        query_kwargs: dict[str, Any] = {
            "IndexName": "gsi_owner_recency",
            "KeyConditionExpression": "owner_key = :owner_key",
            "ExpressionAttributeValues": {":owner_key": _owner_key(auth_context)},
            "ScanIndexForward": False,
            "Limit": limit,
        }
        if cursor:
            query_kwargs["ExclusiveStartKey"] = _decode_cursor(cursor)
        try:
            response = self._sessions_table.query(**query_kwargs)
        except (BotoCoreError, ClientError) as exc:
            raise ChatHistoryError(f"Failed to list sessions: {exc}") from exc

        records = [self._session_from_item(item) for item in response.get("Items", [])]
        if not include_archived:
            records = [record for record in records if record.status != "archived"]

        next_cursor = _encode_cursor(response.get("LastEvaluatedKey"))
        return records, next_cursor

    def rename_session(
        self,
        *,
        session_id: str,
        auth_context: AuthContext,
        title: str,
    ) -> ChatSessionRecord:
        self._require_authorized_session_item(session_id=session_id, auth_context=auth_context)
        now = _now_iso()
        try:
            response = self._sessions_table.update_item(
                Key={"session_id": session_id},
                UpdateExpression="SET title = :title, updated_at = :updated_at",
                ExpressionAttributeValues={":title": title, ":updated_at": now},
                ReturnValues="ALL_NEW",
            )
        except (BotoCoreError, ClientError) as exc:
            raise ChatHistoryError(f"Failed to rename session {session_id!r}: {exc}") from exc
        return self._session_from_item(response["Attributes"])

    def set_session_status(
        self,
        *,
        session_id: str,
        auth_context: AuthContext,
        status: str,
        archive_ttl_days: int = 0,
    ) -> ChatSessionRecord:
        if status not in {"active", "archived"}:
            raise ChatHistoryError(f"Unsupported session status: {status!r}")
        self._require_authorized_session_item(session_id=session_id, auth_context=auth_context)
        now = _now_iso()
        set_clauses = ["#status = :status", "updated_at = :updated_at"]
        expression_values: dict[str, Any] = {":status": status, ":updated_at": now}
        expression_names = {"#status": "status"}
        remove_clause = ""
        if status == "archived":
            set_clauses.append("archived_at = :archived_at")
            expression_values[":archived_at"] = now
            if archive_ttl_days > 0:
                ttl_epoch = int(datetime.now(timezone.utc).timestamp()) + archive_ttl_days * 86400
                set_clauses.append("ttl_epoch_seconds = :ttl_epoch_seconds")
                expression_values[":ttl_epoch_seconds"] = ttl_epoch
        else:
            remove_clause = " REMOVE archived_at, ttl_epoch_seconds"

        try:
            response = self._sessions_table.update_item(
                Key={"session_id": session_id},
                UpdateExpression="SET " + ", ".join(set_clauses) + remove_clause,
                ExpressionAttributeNames=expression_names,
                ExpressionAttributeValues=expression_values,
                ReturnValues="ALL_NEW",
            )
        except (BotoCoreError, ClientError) as exc:
            raise ChatHistoryError(f"Failed to update session {session_id!r} status: {exc}") from exc
        return self._session_from_item(response["Attributes"])

    def delete_session(self, *, session_id: str, auth_context: AuthContext) -> None:
        self._require_authorized_session_item(session_id=session_id, auth_context=auth_context)
        self._delete_all_messages(session_id)
        try:
            self._sessions_table.delete_item(Key={"session_id": session_id})
        except (BotoCoreError, ClientError) as exc:
            raise ChatHistoryError(f"Failed to delete session {session_id!r}: {exc}") from exc

    def _delete_all_messages(self, session_id: str) -> None:
        keys_to_delete: list[dict[str, Any]] = []
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": "session_id = :session_id",
            "ExpressionAttributeValues": {":session_id": session_id},
            "ProjectionExpression": "session_id, sort_key",
        }
        try:
            while True:
                response = self._messages_table.query(**query_kwargs)
                keys_to_delete.extend(
                    {"session_id": item["session_id"], "sort_key": item["sort_key"]}
                    for item in response.get("Items", [])
                )
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                query_kwargs["ExclusiveStartKey"] = last_key
        except (BotoCoreError, ClientError) as exc:
            raise ChatHistoryError(
                f"Failed to list messages for deletion in session {session_id!r}: {exc}"
            ) from exc

        for start in range(0, len(keys_to_delete), _BATCH_DELETE_CHUNK_SIZE):
            chunk = keys_to_delete[start : start + _BATCH_DELETE_CHUNK_SIZE]
            try:
                with self._messages_table.batch_writer() as batch:
                    for key in chunk:
                        batch.delete_item(Key=key)
            except (BotoCoreError, ClientError) as exc:
                raise ChatHistoryError(
                    f"Failed to delete messages for session {session_id!r}: {exc}"
                ) from exc

    ##BRICK 6: Message operations
    def append_message(
        self,
        *,
        session_id: str,
        auth_context: AuthContext,
        role: str,
        content: str,
        request_id: str | None = None,
        route: str | None = None,
        tool_traces: list[dict[str, Any]] | None = None,
        citations: list[dict[str, Any]] | None = None,
        refusal: dict[str, Any] | None = None,
        debug: dict[str, Any] | None = None,
    ) -> ChatMessageRecord:
        session_item = self._require_authorized_session_item(
            session_id=session_id, auth_context=auth_context
        )

        try:
            counter_response = self._sessions_table.update_item(
                Key={"session_id": session_id},
                UpdateExpression="ADD message_count :one",
                ExpressionAttributeValues={":one": 1},
                ReturnValues="UPDATED_NEW",
            )
        except (BotoCoreError, ClientError) as exc:
            raise ChatHistoryError(
                f"Failed to increment message counter for session {session_id!r}: {exc}"
            ) from exc
        sequence = int(counter_response["Attributes"]["message_count"])

        now = _now_iso()
        message_id = f"msg-{uuid.uuid4().hex[:12]}"
        message_item: dict[str, Any] = {
            "session_id": session_id,
            "sort_key": f"MSG#{sequence:012d}",
            "message_id": message_id,
            "tenant_id": auth_context.tenant_id,
            "user_id": auth_context.user_id,
            "role": role,
            "content": content,
            "created_at": now,
        }
        if request_id is not None:
            message_item["request_id"] = request_id
        if route is not None:
            message_item["route"] = route
        if tool_traces:
            message_item["tool_traces"] = tool_traces
        if citations:
            message_item["citations"] = citations
        if refusal is not None:
            message_item["refusal"] = refusal
        if debug:
            message_item["debug"] = debug

        try:
            self._messages_table.put_item(Item=_to_dynamodb_safe(message_item))
        except (BotoCoreError, ClientError) as exc:
            raise ChatHistoryError(
                f"Failed to append message to session {session_id!r}: {exc}"
            ) from exc

        derived_title: str | None = None
        is_first_message = role == "user" and sequence == 1
        if is_first_message and session_item.get("title", DEFAULT_SESSION_TITLE) == DEFAULT_SESSION_TITLE:
            derived_title = derive_session_title(content)

        preview = content.strip()[:140]
        set_clauses = ["updated_at = :updated_at", "last_message_preview = :preview", "last_message_role = :role"]
        expression_values: dict[str, Any] = {":updated_at": now, ":preview": preview, ":role": role}
        if derived_title is not None:
            set_clauses.append("title = :title")
            expression_values[":title"] = derived_title

        try:
            self._sessions_table.update_item(
                Key={"session_id": session_id},
                UpdateExpression="SET " + ", ".join(set_clauses),
                ExpressionAttributeValues=expression_values,
            )
        except (BotoCoreError, ClientError) as exc:
            raise ChatHistoryError(
                f"Failed to update session {session_id!r} after appending message: {exc}"
            ) from exc

        return self._message_from_item(message_item)

    def list_messages(
        self,
        *,
        session_id: str,
        auth_context: AuthContext,
        limit: int = 200,
        cursor: str | None = None,
    ) -> tuple[list[ChatMessageRecord], str | None]:
        self._require_authorized_session_item(session_id=session_id, auth_context=auth_context)
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": "session_id = :session_id",
            "ExpressionAttributeValues": {":session_id": session_id},
            "Limit": limit,
        }
        if cursor:
            query_kwargs["ExclusiveStartKey"] = _decode_cursor(cursor)
        try:
            response = self._messages_table.query(**query_kwargs)
        except (BotoCoreError, ClientError) as exc:
            raise ChatHistoryError(
                f"Failed to list messages for session {session_id!r}: {exc}"
            ) from exc

        records = [self._message_from_item(item) for item in response.get("Items", [])]
        next_cursor = _encode_cursor(response.get("LastEvaluatedKey"))
        return records, next_cursor
