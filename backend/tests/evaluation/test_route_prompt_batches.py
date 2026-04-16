from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import pytest

from backend.app.orchestrator.intent_router import route_message
from backend.app.rag.retriever import KnowledgeRetriever
from backend.app.security.policy_guard import evaluate_input_policy


ROUTE_BATCH_DIR = Path(__file__).parent / "route_batches"
REQUIRED_FIELDS = {
    "id",
    "route_group",
    "message",
    "word_count",
    "expected_http_status",
    "expected_route",
    "expected_tool_name",
    "expected_grounding_mode",
    "expected_citations",
    "expected_tool_traces",
    "expected_refusal_category",
    "expected_answer_contract",
    "must_not",
}
VALID_ROUTES = {"tool", "rag", "clarify", "refuse"}
VALID_TOOLS = {
    None,
    "transaction_lookup",
    "spend_summary",
    "recurring_detection",
    "balances",
    "status_explanation",
}
VALID_GROUNDING_MODES = {None, "tool", "rag", "base"}
VALID_PRESENCE_EXPECTATIONS = {"empty", "non_empty", "any"}
VALID_REFUSAL_CATEGORIES = {
    None,
    "transaction_execution",
    "financial_advice",
    "credit_decision",
    "prompt_extraction",
}

TEST_KB_CHUNKS = [
    {
        "doc_id": "fees_policy",
        "chunk_id": 0,
        "title": "Fees Policy",
        "text": "Payjack fee explanations are available in the help center.",
        "metadata": {"type": "policy", "source_path": "policies/fees.md"},
    }
]


def _load_route_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for batch_path in sorted(ROUTE_BATCH_DIR.glob("*.jsonl")):
        for line_number, line in enumerate(batch_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            case = json.loads(line)
            case["_batch_path"] = str(batch_path)
            case["_line_number"] = line_number
            cases.append(case)
    return cases


ROUTE_CASES = _load_route_cases()


def _case_id(case: dict[str, Any]) -> str:
    return f"{Path(case['_batch_path']).stem}:{case.get('id', case['_line_number'])}"


def _source_context(case: dict[str, Any]) -> str:
    if not case.get("normalization_changed"):
        return ""
    return (
        " Source expectations before normalization were "
        f"route={case.get('source_expected_route')!r}, "
        f"tool={case.get('source_expected_tool_name')!r}, "
        f"grounding={case.get('source_expected_grounding_mode')!r}, "
        f"citations={case.get('source_expected_citations')!r}, "
        f"traces={case.get('source_expected_tool_traces')!r}, "
        f"refusal={case.get('source_expected_refusal_category')!r}."
    )


def _current_expected_behavior(message: str) -> dict[str, Any]:
    policy_decision = evaluate_input_policy(message)
    if not policy_decision.allowed:
        return {
            "expected_route": "refuse",
            "expected_tool_name": None,
            "expected_refusal_category": policy_decision.category,
            "expected_grounding_mode": None,
            "expected_citations": "empty",
            "expected_tool_traces": "empty",
        }

    route_decision = route_message(message)
    if route_decision.route == "tool":
        return {
            "expected_route": "tool",
            "expected_tool_name": route_decision.tool_name,
            "expected_refusal_category": None,
            "expected_grounding_mode": "tool",
            "expected_citations": "empty",
            "expected_tool_traces": "non_empty",
        }
    if route_decision.route == "rag":
        retrieval_result = KnowledgeRetriever(TEST_KB_CHUNKS).retrieve(message)
        grounding_mode = "rag" if retrieval_result.usable_context else "base"
        return {
            "expected_route": "rag",
            "expected_tool_name": None,
            "expected_refusal_category": None,
            "expected_grounding_mode": grounding_mode,
            "expected_citations": "non_empty" if retrieval_result.usable_context else "empty",
            "expected_tool_traces": "empty",
        }

    return {
        "expected_route": route_decision.route,
        "expected_tool_name": None,
        "expected_refusal_category": None,
        "expected_grounding_mode": None,
        "expected_citations": "empty",
        "expected_tool_traces": "empty",
    }


def _safe_session_id(case: dict[str, Any]) -> str:
    raw_id = f"route-batch-{case['id']}"
    return re.sub(r"[^A-Za-z0-9._:-]", "-", raw_id)[:128]


def _assert_tool_payload_shape(tool_name: str, result: dict[str, Any]) -> None:
    if tool_name == "transaction_lookup":
        assert isinstance(result.get("records"), list)
    elif tool_name == "spend_summary":
        assert "total_amount" in result
        assert "transaction_count" in result
        assert isinstance(result.get("grouped_breakdown"), list)
    elif tool_name == "recurring_detection":
        assert isinstance(result.get("records"), list)
    elif tool_name == "balances":
        assert isinstance(result.get("records"), list)
    elif tool_name == "status_explanation":
        assert isinstance(result.get("counts_by_status"), dict)


def _assert_answer_contract(case: dict[str, Any], payload: dict[str, Any]) -> None:
    answer = payload.get("answer", "")
    assert isinstance(answer, str)
    assert answer.strip(), f"{case['id']} returned an empty answer."

    route = case["expected_route"]
    tool_name = case["expected_tool_name"]
    grounding_mode = case["expected_grounding_mode"]

    if route == "tool" and payload["tool_traces"]:
        result = payload["tool_traces"][0].get("result", {})
        if tool_name == "transaction_lookup":
            if result.get("records"):
                assert "Here are the latest matching transactions" in answer
            else:
                assert "could not find any transactions" in answer.lower()
        elif tool_name == "spend_summary":
            assert "Total spend for the selected filters" in answer
        elif tool_name == "recurring_detection":
            if result.get("records"):
                assert "I found these recurring payment patterns" in answer
            else:
                assert "could not find any recurring payments" in answer.lower()
    elif route == "rag":
        if grounding_mode == "rag":
            assert "Based on the accepted Payjack documentation" in answer
        else:
            assert "could not verify" in answer.lower()
            assert "documentation" in answer.lower()
    elif route == "clarify":
        assert "more specific" in answer.lower()
        assert "transaction lookups" in answer.lower()
    elif route == "refuse":
        assert "cannot" in answer.lower()


@pytest.mark.parametrize("case", ROUTE_CASES, ids=_case_id)
def test_route_batch_static_contract(case: dict[str, Any]) -> None:
    missing_fields = REQUIRED_FIELDS - set(case)
    assert not missing_fields, f"{case.get('id', '<missing id>')} is missing fields: {sorted(missing_fields)}"

    assert case["route_group"] == case["expected_route"]
    assert case["expected_route"] in VALID_ROUTES
    assert case["expected_tool_name"] in VALID_TOOLS
    assert case["expected_grounding_mode"] in VALID_GROUNDING_MODES
    assert case["expected_citations"] in VALID_PRESENCE_EXPECTATIONS
    assert case["expected_tool_traces"] in VALID_PRESENCE_EXPECTATIONS
    assert case["expected_refusal_category"] in VALID_REFUSAL_CATEGORIES
    assert isinstance(case["expected_answer_contract"], list)
    assert isinstance(case["must_not"], list)
    assert case["word_count"] == len(case["message"].split())

    current_expectations = _current_expected_behavior(case["message"])
    for field, expected_value in current_expectations.items():
        assert case[field] == expected_value, (
            f"{case['id']} {field} is stale for current backend behavior: "
            f"expected {expected_value!r}, found {case[field]!r}."
            f"{_source_context(case)}"
        )


@pytest.mark.parametrize("case", ROUTE_CASES, ids=_case_id)
def test_route_batch_chat_contract(case: dict[str, Any], test_client, auth_headers) -> None:
    response = test_client.post(
        "/chat",
        headers=auth_headers,
        json={
            "message": case["message"],
            "session_id": _safe_session_id(case),
            "client_request_id": f"{case['id']}-request",
        },
    )

    assert response.status_code == case["expected_http_status"], response.text
    payload = response.json()
    assert payload["route"] == case["expected_route"], _source_context(case)

    tool_traces = payload.get("tool_traces") or []
    if case["expected_tool_traces"] == "non_empty":
        assert tool_traces, f"{case['id']} expected at least one tool trace."
        assert tool_traces[0]["name"] == case["expected_tool_name"]
        _assert_tool_payload_shape(case["expected_tool_name"], tool_traces[0].get("result", {}))
    elif case["expected_tool_traces"] == "empty":
        assert tool_traces == []

    citations = payload.get("citations") or []
    if case["expected_citations"] == "non_empty":
        assert citations, f"{case['id']} expected at least one citation."
    elif case["expected_citations"] == "empty":
        assert citations == []

    if case["expected_refusal_category"] is None:
        assert payload.get("refusal") is None
    else:
        refusal = payload.get("refusal")
        assert refusal is not None
        assert refusal["category"] == case["expected_refusal_category"]

    if case["expected_grounding_mode"] is not None:
        assert payload.get("debug", {}).get("grounding_mode") == case["expected_grounding_mode"]

    _assert_answer_contract(case, payload)
