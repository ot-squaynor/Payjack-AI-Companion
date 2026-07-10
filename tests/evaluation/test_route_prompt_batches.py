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
VALID_ROUTES = {
    "tool",
    "rag",
    "clarify",
    "refuse",
    "deterministic_tool_route",
    "rag_route",
    "hybrid_route",
    "clarification_route",
    "refusal_route",
    "safe_general_route",
}
VALID_TOOLS = {
    None,
    "transaction_lookup",
    "spend_summary",
    "recurring_detection",
    "balances",
    "status_explanation",
    "fee_breakdown",
}
VALID_GROUNDING_MODES = {None, "tool", "rag", "hybrid", "base"}
VALID_PRESENCE_EXPECTATIONS = {"empty", "non_empty", "any"}
VALID_REFUSAL_CATEGORIES = {
    None,
    "transaction_execution",
    "financial_advice",
    "credit_decision",
    "prompt_extraction",
    "money_movement_or_account_execution",
    "personalized_regulated_financial_advice",
    "credit_approval_or_eligibility_decision",
    "fraud_bypass_or_record_tampering",
    "third_party_private_data",
}

TEST_KB_CHUNKS = [
    {
        "doc_id": "fees_policy",
        "chunk_id": 0,
        "title": "Fees Policy",
        "text": "Payjack fee explanations are available in the help center.",
        "metadata": {"type": "policy", "source_path": "policies/fees.md"},
    },
    {
        "doc_id": "jackinvest_overview",
        "chunk_id": 0,
        "title": "JackInvest Overview",
        "text": "JackInvest is a Payjack product area for investment education, product information, fees, and risk explanations.",
        "metadata": {"type": "product", "source_path": "products/jackinvest.md"},
    },
    {
        "doc_id": "payjack_limits",
        "chunk_id": 0,
        "title": "Payjack Transfer Limits",
        "text": "Payjack transfer limits and app usage guidance are documented in the help center.",
        "metadata": {"type": "policy", "source_path": "policies/limits.md"},
    },
    {
        "doc_id": "onboarding_help",
        "chunk_id": 0,
        "title": "Onboarding Help",
        "text": "Payjack onboarding guides explain verification, KYC, app setup, and common onboarding errors.",
        "metadata": {"type": "help", "source_path": "help/onboarding.md"},
    },
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
            "expected_route": "refusal_route",
            "expected_tool_name": None,
            "expected_refusal_category": policy_decision.category,
            "expected_grounding_mode": None,
            "expected_citations": "empty",
            "expected_tool_traces": "empty",
        }

    route_decision = route_message(message)
    if route_decision.route in {"deterministic_tool_route", "hybrid_route"}:
        return {
            "expected_route": route_decision.route,
            "expected_tool_name": route_decision.tool_name,
            "expected_refusal_category": None,
            "expected_grounding_mode": None if route_decision.route == "hybrid_route" else "tool",
            "expected_citations": "any" if route_decision.route == "hybrid_route" else "empty",
            "expected_tool_traces": "non_empty",
        }
    if route_decision.route == "rag_route":
        retrieval_result = KnowledgeRetriever(TEST_KB_CHUNKS).retrieve(message)
        grounding_mode = "rag" if retrieval_result.usable_context else "base"
        return {
            "expected_route": "rag_route",
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
        "expected_grounding_mode": "base" if route_decision.route == "safe_general_route" else None,
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
    elif tool_name == "fee_breakdown":
        assert isinstance(result.get("records"), list)
        assert "total_amount" in result


def _assert_answer_contract(case_id: str, expected: dict[str, Any], payload: dict[str, Any]) -> None:
    answer = payload.get("answer", "")
    assert isinstance(answer, str)
    assert answer.strip(), f"{case_id} returned an empty answer."

    route = expected["expected_route"]
    tool_name = expected["expected_tool_name"]
    grounding_mode = expected["expected_grounding_mode"]

    if route in {"deterministic_tool_route", "hybrid_route"} and payload["tool_traces"]:
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
        elif tool_name == "fee_breakdown":
            assert "fee-like transaction" in answer.lower() or "could not find fee-like transactions" in answer.lower()
    elif route == "rag_route":
        if grounding_mode == "rag":
            assert "Based on the accepted Payjack documentation" in answer
        else:
            assert "could not verify" in answer.lower()
            assert "documentation" in answer.lower()
    elif route == "clarification_route":
        assert "?" in answer
    elif route == "refusal_route":
        assert "cannot" in answer.lower()
    elif route == "safe_general_route":
        assert "general" in answer.lower()


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

    assert isinstance(case["message"], str)


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
    expected = _current_expected_behavior(case["message"])
    assert payload["route"] == expected["expected_route"], _source_context(case)

    tool_traces = payload.get("tool_traces") or []
    if expected["expected_tool_traces"] == "non_empty":
        assert tool_traces, f"{case['id']} expected at least one tool trace."
        assert tool_traces[0]["name"] == expected["expected_tool_name"]
        _assert_tool_payload_shape(expected["expected_tool_name"], tool_traces[0].get("result", {}))
    elif expected["expected_tool_traces"] == "empty":
        assert tool_traces == []

    citations = payload.get("citations") or []
    if expected["expected_citations"] == "non_empty":
        assert citations, f"{case['id']} expected at least one citation."
    elif expected["expected_citations"] == "empty":
        assert citations == []

    if expected["expected_refusal_category"] is None:
        assert payload.get("refusal") is None
    else:
        refusal = payload.get("refusal")
        assert refusal is not None
        assert refusal["category"] == expected["expected_refusal_category"]

    if expected["expected_grounding_mode"] is not None:
        assert payload.get("debug", {}).get("grounding_mode") == expected["expected_grounding_mode"]

    _assert_answer_contract(case["id"], expected, payload)
