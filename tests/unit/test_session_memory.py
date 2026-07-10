from app.memory.session_memory import (
    InMemorySessionMemoryStore,
    ToolMemoryFact,
    resolve_contextual_followup,
)


def test_resolves_spend_currency_followup_from_last_tool_fact() -> None:
    store = InMemorySessionMemoryStore()
    store.record_exchange(
        session_id="session-1",
        user_message="how much have I spent in total",
        assistant_answer="Total spend for the selected filters is [redacted-phone].65.",
        request_id="req-1",
        route="deterministic_tool_route",
        tool_facts=[
            ToolMemoryFact(
                name="spend_summary",
                arguments={},
                result={
                    "total_amount": "123456789.65",
                    "transaction_count": 11343,
                    "currency_breakdown": {"GHS": "123456789.65"},
                },
            )
        ],
    )

    resolution = resolve_contextual_followup("so how many cedis", store.get("session-1"))

    assert resolution is not None
    assert resolution.route == "memory_context_route"
    assert "123456789.65 GHS" in resolution.answer
    assert "11343 transactions" in resolution.answer
    assert "[redacted-phone]" not in resolution.answer


def test_ignores_followup_without_tool_memory() -> None:
    store = InMemorySessionMemoryStore()

    resolution = resolve_contextual_followup("so how many cedis", store.get("missing-session"))

    assert resolution is None

