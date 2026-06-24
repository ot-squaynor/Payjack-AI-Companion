# backend/tests/integration/test_tools_route.py
# 2026-06-24
"""Purpose: Integration tests for the POST /tools/invoke endpoint."""

from __future__ import annotations

import pytest
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


# ── UI contract tests (date_from/date_to and other UI-specific arg names) ──────


def test_transaction_lookup_with_ui_date_range(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "transaction_lookup", "arguments": {
            "date_from": "2026-01-01", "date_to": "2026-03-31", "limit": 5,
        }},
    )
    assert response.status_code == 200
    assert "records" in response.json()["payload"]


def test_transaction_lookup_with_ui_amount_range(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "transaction_lookup", "arguments": {
            "amount_min": "10.00", "amount_max": "500.00",
        }},
    )
    assert response.status_code == 200
    assert "records" in response.json()["payload"]


def test_spend_summary_with_ui_date_range_and_group_by(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "spend_summary", "arguments": {
            "date_from": "2026-01-01", "date_to": "2026-03-31", "group_by": "category",
        }},
    )
    assert response.status_code == 200
    assert "grouped_breakdown" in response.json()["payload"]


def test_recurring_detection_with_ui_cadence_confidence(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "recurring_detection", "arguments": {
            "cadence": "monthly", "confidence": "high",
        }},
    )
    assert response.status_code == 200
    assert "records" in response.json()["payload"]


def test_status_explanation_with_ui_date_range(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "status_explanation", "arguments": {
            "date_from": "2026-01-01", "date_to": "2026-03-31",
        }},
    )
    assert response.status_code == 200
    assert "counts_by_status" in response.json()["payload"]


def test_fee_breakdown_with_ui_date_range_and_limit(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "fee_breakdown", "arguments": {
            "date_from": "2026-01-01", "date_to": "2026-03-31", "limit": 3,
        }},
    )
    assert response.status_code == 200
    assert "total_amount" in response.json()["payload"]


def test_invalid_date_returns_422(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "transaction_lookup", "arguments": {"date_from": "not-a-date"}},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "validation_error"
    assert "date_from" in detail["message"]


def test_balances_missing_accounts_artifact_returns_503(
    test_client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.repository.processed_store import ProcessedStoreError

    def raise_store_error() -> None:
        raise ProcessedStoreError("No artifact named 'accounts' exists in the processed manifest.")

    dependencies = test_client.app.state.dependencies
    monkeypatch.setattr(dependencies.tool_registry.store, "get_accounts", raise_store_error)

    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "balances", "arguments": {}},
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "missing_artifact"
    assert "accounts" in detail["message"]


def test_original_internal_arg_names_still_work(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    # Regression: callers using the internal schema (start_date/end_date) must keep working.
    response = test_client.post(
        "/tools/invoke",
        headers=auth_headers,
        json={"tool": "transaction_lookup", "arguments": {
            "start_date": "2026-01-01", "end_date": "2026-03-31",
        }},
    )
    assert response.status_code == 200
    assert "records" in response.json()["payload"]
