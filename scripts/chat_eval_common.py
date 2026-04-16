# scripts/chat_eval_common.py
# 2026-04-14
"""Purpose: Share local and live chat evaluation helpers across CLI probes."""

from __future__ import annotations

##BRICK 1: Imports, repository bootstrap, and env loading
import json
from pathlib import Path
import sys
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.env import load_local_env


load_local_env()


##BRICK 2: Request helpers
def build_headers(
    *,
    user_id: str,
    tenant_id: str,
    roles: str,
    account_ids: str,
) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-payjack-user-id": user_id,
        "x-payjack-tenant-id": tenant_id,
        "x-payjack-roles": roles,
        "x-payjack-account-ids": account_ids,
    }


def _post_chat_live(
    *,
    api_base_url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    request = urllib_request.Request(
        url=f"{api_base_url.rstrip('/')}/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Live chat request failed with {exc.code}: {detail}") from exc


def _decode_response_body(body: str) -> dict[str, Any] | str:
    try:
        decoded = json.loads(body)
    except json.JSONDecodeError:
        return body
    return decoded if isinstance(decoded, dict) else body


def _request_chat_live(
    *,
    api_base_url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> tuple[int, dict[str, Any] | str]:
    request = urllib_request.Request(
        url=f"{api_base_url.rstrip('/')}/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(request) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, _decode_response_body(body)
    except urllib_error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, _decode_response_body(body)


def _post_chat_inproc(
    *,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as client:
        response = client.post("/chat", headers=headers, json=payload)
        if not response.is_success:
            raise RuntimeError(
                f"In-process chat request failed with {response.status_code}: {response.text}"
            )
        return response.json()


def _request_chat_inproc(
    *,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> tuple[int, dict[str, Any] | str]:
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as client:
        response = client.post("/chat", headers=headers, json=payload)
        try:
            body: dict[str, Any] | str = response.json()
        except ValueError:
            body = response.text
        return response.status_code, body


def request_chat(
    *,
    message: str,
    session_id: str,
    api_base_url: str | None,
    user_id: str,
    tenant_id: str,
    roles: str,
    account_ids: str,
    client_request_id: str | None = None,
) -> tuple[int, dict[str, Any] | str]:
    payload: dict[str, Any] = {
        "message": message,
        "session_id": session_id,
    }
    if client_request_id:
        payload["client_request_id"] = client_request_id

    headers = build_headers(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=roles,
        account_ids=account_ids,
    )
    if api_base_url:
        return _request_chat_live(
            api_base_url=api_base_url,
            payload=payload,
            headers=headers,
        )
    return _request_chat_inproc(payload=payload, headers=headers)


def post_chat(
    *,
    message: str,
    session_id: str,
    api_base_url: str | None,
    user_id: str,
    tenant_id: str,
    roles: str,
    account_ids: str,
    client_request_id: str | None = None,
) -> dict[str, Any]:
    status_code, body = request_chat(
        message=message,
        session_id=session_id,
        api_base_url=api_base_url,
        user_id=user_id,
        tenant_id=tenant_id,
        roles=roles,
        account_ids=account_ids,
        client_request_id=client_request_id,
    )
    if status_code < 200 or status_code >= 300:
        raise RuntimeError(f"Chat request failed with {status_code}: {body}")
    if not isinstance(body, dict):
        raise RuntimeError(f"Chat request returned a non-JSON object body: {body}")
    return body


##BRICK 3: Result summarization and validation
def summarize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    debug = payload.get("debug") or {}
    answer = str(payload.get("answer", "")).replace("\n", " ").strip()
    return {
        "request_id": payload.get("request_id"),
        "route": payload.get("route"),
        "model_id": debug.get("model_id"),
        "llm_request_id": debug.get("llm_request_id"),
        "citation_count": len(payload.get("citations") or []),
        "tool_trace_count": len(payload.get("tool_traces") or []),
        "estimated_cost_usd": debug.get("estimated_cost_usd"),
        "answer_preview": answer[:200],
    }


def validate_payload(
    payload: dict[str, Any],
    *,
    expected_route: str | None = None,
    expected_model_id: str | None = None,
    require_citations: bool = False,
    require_tool_traces: bool = False,
) -> list[str]:
    debug = payload.get("debug") or {}
    failures: list[str] = []

    if expected_route and payload.get("route") != expected_route:
        failures.append(
            f"expected route '{expected_route}' but received '{payload.get('route')}'"
        )
    if expected_model_id and debug.get("model_id") != expected_model_id:
        failures.append(
            f"expected model_id '{expected_model_id}' but received '{debug.get('model_id')}'"
        )
    if require_citations and not payload.get("citations"):
        failures.append("expected at least one citation but received none")
    if require_tool_traces and not payload.get("tool_traces"):
        failures.append("expected at least one tool trace but received none")

    return failures
