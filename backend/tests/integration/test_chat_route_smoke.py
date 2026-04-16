import importlib

from fastapi.testclient import TestClient


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


def test_api_prefixed_routes_mirror_direct_routes(test_client, auth_headers) -> None:
    health_response = test_client.get("/api/health")
    ready_response = test_client.get("/api/ready")
    chat_response = test_client.post(
        "/api/chat",
        headers=auth_headers,
        json={"message": "Show my last 2 transactions", "session_id": "session-api-prefix-1"},
    )

    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"
    assert ready_response.status_code == 200
    assert ready_response.json()["status"] == "ready"
    assert chat_response.status_code == 200
    payload = chat_response.json()
    assert payload["route"] == "tool"
    assert payload["tool_traces"][0]["name"] == "transaction_lookup"


def test_lambda_handler_imports() -> None:
    from app.lambda_handler import handler

    assert handler is not None


def test_chat_route_returns_grounded_doc_response(test_client, auth_headers) -> None:
    response = test_client.post(
        "/chat",
        headers=auth_headers,
        json={"message": "What is the Payjack fee policy?", "session_id": "session-test-1b"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "rag"
    assert payload["debug"]["grounding_mode"] == "rag"
    assert payload["citations"]
    assert payload["citations"][0]["title"] == "Fees Policy"


def test_chat_route_falls_back_when_docs_are_not_reliable(test_client, auth_headers) -> None:
    response = test_client.post(
        "/chat",
        headers=auth_headers,
        json={"message": "What are the Payjack features?", "session_id": "session-test-1c"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "rag"
    assert payload["debug"]["grounding_mode"] == "base"
    assert payload["citations"] == []
    assert payload["debug"]["accepted_citation_count"] == 0
    assert "documentation" in payload["answer"].lower()


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


def test_chat_route_handles_unavailable_tool_data_gracefully(
    configured_test_env,
    auth_headers,
    monkeypatch,
) -> None:
    missing_processed_root = configured_test_env["runtime_root"] / "missing-processed"
    monkeypatch.setenv("PROCESSED_LOCAL_ROOT", str(missing_processed_root))
    monkeypatch.setenv("KB_CHUNKS_PATH", str(configured_test_env["kb_chunks_path"]))
    monkeypatch.setenv("USE_MOCK_BEDROCK", "true")
    monkeypatch.setenv("USE_LOCAL_RAG", "true")
    monkeypatch.setenv("ENABLE_DEBUG_TRACES", "true")

    import app.main as main_module

    importlib.reload(main_module)
    with TestClient(main_module.create_app()) as client:
        response = client.post(
            "/chat",
            headers=auth_headers,
            json={"message": "Look up my transactions from April to May", "session_id": "session-test-3"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "tool"
    assert payload["tool_traces"] == []
    assert payload["debug"]["grounding_mode"] == "tool"
    assert "processed artifacts" in payload["answer"].lower()
