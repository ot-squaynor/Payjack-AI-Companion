def test_chat_route_returns_tool_backed_response(test_client, auth_headers) -> None:
    response = test_client.post(
        "/chat",
        headers=auth_headers,
        json={"message": "Show my last 2 transactions", "session_id": "session-test-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "tool"
    assert payload["tool_traces"][0]["name"] == "transaction_lookup"
    assert "Fresh Market" in payload["answer"]
    assert "Utility Co" not in payload["answer"]


def test_chat_route_refuses_disallowed_requests(test_client, auth_headers) -> None:
    response = test_client.post(
        "/chat",
        headers=auth_headers,
        json={"message": "Send money to another account", "session_id": "session-test-2"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "refuse"
    assert payload["refusal"]["category"] == "transaction_execution"
