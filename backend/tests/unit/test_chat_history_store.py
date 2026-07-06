import pytest

from app.chat_history.store import (
    ChatHistorySessionNotFoundError,
    ChatHistoryStore,
    derive_session_title,
)
from app.security.auth_context import AuthContext
from tests.conftest import CHAT_MESSAGES_TEST_TABLE, CHAT_SESSIONS_TEST_TABLE


AUTH_A = AuthContext(user_id="user-a", tenant_id="tenant-1")
AUTH_B = AuthContext(user_id="user-b", tenant_id="tenant-2")


@pytest.fixture
def store(dynamodb_chat_tables) -> ChatHistoryStore:
    return ChatHistoryStore(
        sessions_table_name=CHAT_SESSIONS_TEST_TABLE,
        messages_table_name=CHAT_MESSAGES_TEST_TABLE,
        aws_region="eu-west-2",
    )


def test_derive_session_title_truncates_long_messages() -> None:
    long_message = "a" * 100
    title = derive_session_title(long_message)
    assert title == "a" * 60 + "…"


def test_derive_session_title_ignores_tool_echo_messages() -> None:
    assert derive_session_title("📊 spend summary card") == "New conversation"


def test_derive_session_title_short_message_is_unchanged() -> None:
    assert derive_session_title("How much did I spend?") == "How much did I spend?"


def test_create_and_get_session(store: ChatHistoryStore) -> None:
    created = store.create_session(auth_context=AUTH_A, title="My chat")

    fetched = store.get_session(session_id=created.session_id, auth_context=AUTH_A)

    assert fetched is not None
    assert fetched.session_id == created.session_id
    assert fetched.title == "My chat"
    assert fetched.status == "active"
    assert fetched.message_count == 0


def test_get_or_create_session_is_idempotent(store: ChatHistoryStore) -> None:
    first = store.get_or_create_session(session_id="session-fixed-1", auth_context=AUTH_A)
    second = store.get_or_create_session(session_id="session-fixed-1", auth_context=AUTH_A)

    assert first.session_id == second.session_id == "session-fixed-1"
    assert first.created_at == second.created_at


def test_get_session_returns_none_for_missing_session(store: ChatHistoryStore) -> None:
    assert store.get_session(session_id="does-not-exist", auth_context=AUTH_A) is None


def test_user_cannot_read_another_users_session(store: ChatHistoryStore) -> None:
    created = store.create_session(auth_context=AUTH_A)

    assert store.get_session(session_id=created.session_id, auth_context=AUTH_B) is None


def test_append_message_auto_derives_title_from_first_user_message(store: ChatHistoryStore) -> None:
    created = store.create_session(auth_context=AUTH_A)

    store.append_message(
        session_id=created.session_id,
        auth_context=AUTH_A,
        role="user",
        content="How much have I spent this month?",
    )
    store.append_message(
        session_id=created.session_id,
        auth_context=AUTH_A,
        role="assistant",
        content="You spent 120 GHS this month.",
        request_id="req-1",
        route="deterministic_tool_route",
    )

    session = store.get_session(session_id=created.session_id, auth_context=AUTH_A)
    assert session is not None
    assert session.title == "How much have I spent this month?"
    assert session.message_count == 2
    assert session.last_message_role == "assistant"
    assert session.last_message_preview == "You spent 120 GHS this month."


def test_list_messages_returns_messages_in_append_order(store: ChatHistoryStore) -> None:
    created = store.create_session(auth_context=AUTH_A)
    store.append_message(session_id=created.session_id, auth_context=AUTH_A, role="user", content="first")
    store.append_message(
        session_id=created.session_id,
        auth_context=AUTH_A,
        role="assistant",
        content="second",
        tool_traces=[{"name": "spend_summary", "arguments": {}, "result": {}, "warnings": [], "artifact_version": None}],
        citations=[{"doc_id": "doc-1", "title": "Doc", "snippet": "...", "score": 0.9, "metadata": {}}],
    )
    store.append_message(session_id=created.session_id, auth_context=AUTH_A, role="user", content="third")

    messages, next_cursor = store.list_messages(session_id=created.session_id, auth_context=AUTH_A)

    assert [m.content for m in messages] == ["first", "second", "third"]
    assert messages[1].tool_traces[0]["name"] == "spend_summary"
    assert messages[1].citations[0]["doc_id"] == "doc-1"
    assert next_cursor is None


def test_list_messages_denies_access_for_other_users_session(store: ChatHistoryStore) -> None:
    created = store.create_session(auth_context=AUTH_A)
    store.append_message(session_id=created.session_id, auth_context=AUTH_A, role="user", content="hello")

    with pytest.raises(ChatHistorySessionNotFoundError):
        store.list_messages(session_id=created.session_id, auth_context=AUTH_B)


def test_list_sessions_orders_by_recency_descending(store: ChatHistoryStore) -> None:
    first = store.create_session(auth_context=AUTH_A)
    second = store.create_session(auth_context=AUTH_A)
    # Bump `second`'s updated_at ahead of `first` by appending a message to it.
    store.append_message(session_id=second.session_id, auth_context=AUTH_A, role="user", content="hi")

    sessions, _ = store.list_sessions(auth_context=AUTH_A)

    assert [s.session_id for s in sessions] == [second.session_id, first.session_id]


def test_list_sessions_isolated_per_user(store: ChatHistoryStore) -> None:
    store.create_session(auth_context=AUTH_A)
    store.create_session(auth_context=AUTH_B)

    sessions_a, _ = store.list_sessions(auth_context=AUTH_A)
    sessions_b, _ = store.list_sessions(auth_context=AUTH_B)

    assert len(sessions_a) == 1
    assert len(sessions_b) == 1
    assert sessions_a[0].session_id != sessions_b[0].session_id


def test_rename_session(store: ChatHistoryStore) -> None:
    created = store.create_session(auth_context=AUTH_A)

    renamed = store.rename_session(session_id=created.session_id, auth_context=AUTH_A, title="Renamed")

    assert renamed.title == "Renamed"


def test_rename_session_denies_access_for_other_users_session(store: ChatHistoryStore) -> None:
    created = store.create_session(auth_context=AUTH_A)

    with pytest.raises(ChatHistorySessionNotFoundError):
        store.rename_session(session_id=created.session_id, auth_context=AUTH_B, title="Hijacked")


def test_archive_hides_session_from_default_list_but_not_include_archived(store: ChatHistoryStore) -> None:
    created = store.create_session(auth_context=AUTH_A)

    store.set_session_status(session_id=created.session_id, auth_context=AUTH_A, status="archived")

    active_sessions, _ = store.list_sessions(auth_context=AUTH_A, include_archived=False)
    all_sessions, _ = store.list_sessions(auth_context=AUTH_A, include_archived=True)

    assert active_sessions == []
    assert len(all_sessions) == 1
    assert all_sessions[0].status == "archived"
    assert all_sessions[0].archived_at is not None


def test_reactivate_session_clears_archived_at(store: ChatHistoryStore) -> None:
    created = store.create_session(auth_context=AUTH_A)
    store.set_session_status(session_id=created.session_id, auth_context=AUTH_A, status="archived")

    reactivated = store.set_session_status(
        session_id=created.session_id, auth_context=AUTH_A, status="active"
    )

    assert reactivated.status == "active"
    assert reactivated.archived_at is None


def test_delete_session_cascades_to_messages(store: ChatHistoryStore) -> None:
    created = store.create_session(auth_context=AUTH_A)
    store.append_message(session_id=created.session_id, auth_context=AUTH_A, role="user", content="hi")

    store.delete_session(session_id=created.session_id, auth_context=AUTH_A)

    assert store.get_session(session_id=created.session_id, auth_context=AUTH_A) is None
    with pytest.raises(ChatHistorySessionNotFoundError):
        store.list_messages(session_id=created.session_id, auth_context=AUTH_A)


def test_delete_session_denies_access_for_other_users_session(store: ChatHistoryStore) -> None:
    created = store.create_session(auth_context=AUTH_A)

    with pytest.raises(ChatHistorySessionNotFoundError):
        store.delete_session(session_id=created.session_id, auth_context=AUTH_B)


def test_delete_missing_session_raises_not_found(store: ChatHistoryStore) -> None:
    with pytest.raises(ChatHistorySessionNotFoundError):
        store.delete_session(session_id="does-not-exist", auth_context=AUTH_A)
