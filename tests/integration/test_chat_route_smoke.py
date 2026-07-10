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
    assert payload["route"] == "deterministic_tool_route"
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
    assert payload["route"] == "deterministic_tool_route"
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
    assert payload["route"] == "rag_route"
    assert payload["debug"]["grounding_mode"] == "rag"
    assert payload["citations"]
    assert payload["citations"][0]["title"] == "Fees Policy"


def test_chat_route_allows_transfer_limit_doc_response(test_client, auth_headers) -> None:
    response = test_client.post(
        "/chat",
        headers=auth_headers,
        json={"message": "What is the Payjack daily transfer limit?", "session_id": "session-transfer-limit-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "rag_route"
    assert payload["refusal"] is None
    assert payload["citations"]
    assert payload["citations"][0]["title"] == "Payjack Transfer Limits"


def test_chat_route_falls_back_when_docs_are_not_reliable(test_client, auth_headers) -> None:
    response = test_client.post(
        "/chat",
        headers=auth_headers,
        json={"message": "What are the Payjack features?", "session_id": "session-test-1c"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "rag_route"
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
    assert payload["route"] == "refusal_route"
    assert payload["refusal"]["category"] == "money_movement_or_account_execution"


def test_chat_route_allows_safe_general_questions(test_client, auth_headers) -> None:
    response = test_client.post(
        "/chat",
        headers=auth_headers,
        json={"message": "Explain compound interest simply.", "session_id": "session-general-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "safe_general_route"
    assert payload["refusal"] is None
    assert payload["debug"]["grounding_mode"] == "base"


def test_chat_route_handles_hybrid_fee_question(test_client, auth_headers) -> None:
    response = test_client.post(
        "/chat",
        headers=auth_headers,
        json={"message": "Why was I charged this fee?", "session_id": "session-hybrid-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "hybrid_route"
    assert payload["tool_traces"][0]["name"] == "fee_breakdown"
    assert payload["refusal"] is None


def test_chat_route_resolves_spend_followup_from_session_memory(test_client, auth_headers) -> None:
    session_id = "session-memory-spend-1"
    first_response = test_client.post(
        "/chat",
        headers=auth_headers,
        json={"message": "How much have I spent in total?", "session_id": session_id},
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["route"] == "deterministic_tool_route"
    assert first_payload["tool_traces"][0]["name"] == "spend_summary"

    followup_response = test_client.post(
        "/chat",
        headers=auth_headers,
        json={"message": "so how many GHS", "session_id": session_id},
    )

    assert followup_response.status_code == 200
    followup_payload = followup_response.json()
    assert followup_payload["route"] == "memory_context_route"
    assert "73.00 GHS" in followup_payload["answer"]
    assert "3 transactions" in followup_payload["answer"]
    assert followup_payload["debug"]["memory_context"]["source_tool_name"] == "spend_summary"


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
    assert payload["route"] == "deterministic_tool_route"
    assert payload["tool_traces"] == []
    assert payload["debug"]["grounding_mode"] == "tool"
    assert "processed artifacts" in payload["answer"].lower()
