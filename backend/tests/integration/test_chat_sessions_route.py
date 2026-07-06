def test_create_session_returns_default_title(test_client, auth_headers) -> None:
    response = test_client.post("/chat/sessions", headers=auth_headers, json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "New conversation"
    assert payload["status"] == "active"
    assert payload["message_count"] == 0


def test_create_session_with_explicit_title(test_client, auth_headers) -> None:
    response = test_client.post(
        "/chat/sessions", headers=auth_headers, json={"title": "Budgeting help"}
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Budgeting help"


def test_get_session_not_found_returns_404(test_client, auth_headers) -> None:
    response = test_client.get("/chat/sessions/does-not-exist", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"


def test_rename_session(test_client, auth_headers) -> None:
    created = test_client.post("/chat/sessions", headers=auth_headers, json={}).json()

    response = test_client.patch(
        f"/chat/sessions/{created['session_id']}",
        headers=auth_headers,
        json={"title": "Renamed chat"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Renamed chat"


def test_archive_then_reactivate_session(test_client, auth_headers) -> None:
    created = test_client.post("/chat/sessions", headers=auth_headers, json={}).json()
    session_id = created["session_id"]

    archive_response = test_client.patch(
        f"/chat/sessions/{session_id}", headers=auth_headers, json={"status": "archived"}
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"

    default_list = test_client.get("/chat/sessions", headers=auth_headers).json()
    assert session_id not in [s["session_id"] for s in default_list["sessions"]]

    with_archived_list = test_client.get(
        "/chat/sessions", headers=auth_headers, params={"include_archived": "true"}
    ).json()
    assert session_id in [s["session_id"] for s in with_archived_list["sessions"]]

    reactivate_response = test_client.patch(
        f"/chat/sessions/{session_id}", headers=auth_headers, json={"status": "active"}
    )
    assert reactivate_response.status_code == 200
    assert reactivate_response.json()["status"] == "active"


def test_update_session_requires_title_or_status(test_client, auth_headers) -> None:
    created = test_client.post("/chat/sessions", headers=auth_headers, json={}).json()

    response = test_client.patch(
        f"/chat/sessions/{created['session_id']}", headers=auth_headers, json={}
    )

    assert response.status_code == 422


def test_delete_session_then_get_returns_404(test_client, auth_headers) -> None:
    created = test_client.post("/chat/sessions", headers=auth_headers, json={}).json()
    session_id = created["session_id"]

    delete_response = test_client.delete(f"/chat/sessions/{session_id}", headers=auth_headers)
    assert delete_response.status_code == 200
    assert delete_response.json() == {"session_id": session_id, "deleted": True}

    get_response = test_client.get(f"/chat/sessions/{session_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_user_cannot_see_or_mutate_another_users_session(
    test_client, auth_headers, auth_headers_other_user
) -> None:
    created = test_client.post("/chat/sessions", headers=auth_headers, json={}).json()
    session_id = created["session_id"]

    get_response = test_client.get(f"/chat/sessions/{session_id}", headers=auth_headers_other_user)
    assert get_response.status_code == 404

    list_response = test_client.get("/chat/sessions", headers=auth_headers_other_user)
    assert session_id not in [s["session_id"] for s in list_response.json()["sessions"]]

    rename_response = test_client.patch(
        f"/chat/sessions/{session_id}",
        headers=auth_headers_other_user,
        json={"title": "Hijacked"},
    )
    assert rename_response.status_code == 404

    delete_response = test_client.delete(f"/chat/sessions/{session_id}", headers=auth_headers_other_user)
    assert delete_response.status_code == 404


def test_chat_auto_creates_session_with_derived_title_and_messages(
    test_client, auth_headers
) -> None:
    session_id = "session-auto-create-1"
    chat_response = test_client.post(
        "/chat",
        headers=auth_headers,
        json={"message": "Show my last 2 transactions", "session_id": session_id},
    )
    assert chat_response.status_code == 200

    session_response = test_client.get(f"/chat/sessions/{session_id}", headers=auth_headers)
    assert session_response.status_code == 200
    session_payload = session_response.json()
    assert session_payload["title"] == "Show my last 2 transactions"
    assert session_payload["message_count"] == 2
    assert session_payload["last_message_role"] == "assistant"

    messages_response = test_client.get(
        f"/chat/sessions/{session_id}/messages", headers=auth_headers
    )
    assert messages_response.status_code == 200
    messages_payload = messages_response.json()
    assert messages_payload["session_id"] == session_id
    messages = messages_payload["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "Show my last 2 transactions"
    assert messages[1]["route"] == "deterministic_tool_route"
    assert messages[1]["tool_traces"][0]["name"] == "transaction_lookup"


def test_list_messages_for_missing_session_returns_404(test_client, auth_headers) -> None:
    response = test_client.get("/chat/sessions/does-not-exist/messages", headers=auth_headers)

    assert response.status_code == 404


def test_list_sessions_orders_by_recency_descending(test_client, auth_headers) -> None:
    test_client.post(
        "/chat", headers=auth_headers, json={"message": "hi", "session_id": "session-recency-1"}
    )
    test_client.post(
        "/chat", headers=auth_headers, json={"message": "hi", "session_id": "session-recency-2"}
    )
    test_client.post(
        "/chat", headers=auth_headers, json={"message": "hi", "session_id": "session-recency-3"}
    )

    response = test_client.get("/chat/sessions", headers=auth_headers)

    assert response.status_code == 200
    session_ids = [s["session_id"] for s in response.json()["sessions"]]
    ordered_indices = [session_ids.index(sid) for sid in ("session-recency-3", "session-recency-2", "session-recency-1")]
    assert ordered_indices == sorted(ordered_indices)
