# backend/tests/integration/test_tools_route.py
# 2026-06-24
"""Purpose: Integration tests for the POST /tools/invoke endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_balances_returns_account_data(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "balances", "arguments": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "balances"
    assert "records" in payload["payload"]
    assert isinstance(payload["payload"]["records"], list)
    assert len(payload["payload"]["records"]) >= 1
    assert payload["payload"]["records"][0]["account_id"] == "acc-001"


def test_transaction_lookup_with_limit(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "transaction_lookup", "arguments": {"limit": 2}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "transaction_lookup"
    assert "records" in payload["payload"]
    assert len(payload["payload"]["records"]) <= 2


def test_unknown_tool_returns_422(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "wire_transfer", "arguments": {}},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "validation_error"
    assert "wire_transfer" in detail["message"]


def test_account_scoping_enforced(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    # auth_headers scopes to acc-001 only; requesting acc-002 should be denied
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "balances", "arguments": {"account_ids": ["acc-002"]}},
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "access_denied"


def test_spend_summary_group_by_category(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "spend_summary", "arguments": {"group_by": "category"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "spend_summary"
    assert "grouped_breakdown" in payload["payload"]


def test_api_prefixed_tools_route(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/api/tools/invoke",
        headers=auth_headers,
        json={"tool": "balances", "arguments": {}},
    )

    assert response.status_code == 200
    assert response.json()["tool"] == "balances"


def test_response_has_latency_and_request_id(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "balances", "arguments": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["latency_ms"], float)
    assert len(payload["request_id"]) > 0


def test_recurring_detection_returns_patterns(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "recurring_detection", "arguments": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "recurring_detection"
    assert "records" in payload["payload"]
    assert "match_count" in payload["payload"]


def test_fee_breakdown_returns_fees(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "fee_breakdown", "arguments": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "fee_breakdown"
    assert "total_amount" in payload["payload"]
    assert "records" in payload["payload"]


def test_status_explanation_returns_counts(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "status_explanation", "arguments": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "status_explanation"
    assert "counts_by_status" in payload["payload"]
