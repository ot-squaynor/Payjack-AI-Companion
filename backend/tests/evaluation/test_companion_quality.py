from app.orchestrator.intent_router import route_message


ALLOWED_RAG_CASES = {
    "What is JackInvest?": "rag_route",
    "What are PayJack's transfer limits?": "rag_route",
    "How does onboarding work?": "rag_route",
    "Where can I find PayJack fee explanations?": "rag_route",
}

ALLOWED_TOOL_CASES = {
    "Summarise my spending this month.": ("deterministic_tool_route", "spend_summary"),
    "How much did I spend on groceries last month?": ("deterministic_tool_route", "spend_summary"),
    "What subscriptions do I have?": ("deterministic_tool_route", "recurring_detection"),
    "Show my last 2 transactions.": ("deterministic_tool_route", "transaction_lookup"),
    "Show my balances.": ("deterministic_tool_route", "balances"),
}

ALLOWED_HYBRID_CASES = {
    "Why was I charged this fee?": "fee_breakdown",
    "Explain this JackInvest transaction.": "transaction_lookup",
    "Why did my subscription increase under the PayJack fee policy?": "recurring_detection",
}

CLARIFICATION_CASES = (
    "What happened?",
    "Is this good?",
    "Can you check it?",
    "Why is this high?",
)

SAFE_GENERAL_CASES = (
    "Explain the risks of mutual funds.",
    "What is compound interest?",
    "Give me three tips for writing a professional email.",
    "Explain APIs in simple terms.",
)


def test_allowed_rag_questions_are_not_refused() -> None:
    for message, route in ALLOWED_RAG_CASES.items():
        decision = route_message(message)

        assert decision.route == route
        assert decision.allowed is True
        assert decision.requires_policy_docs is True


def test_allowed_deterministic_tool_questions_are_not_refused() -> None:
    for message, (route, tool_name) in ALLOWED_TOOL_CASES.items():
        decision = route_message(message)

        assert decision.route == route
        assert decision.allowed is True
        assert decision.tool_name == tool_name


def test_allowed_hybrid_questions_are_not_refused() -> None:
    for message, tool_name in ALLOWED_HYBRID_CASES.items():
        decision = route_message(message)

        assert decision.route == "hybrid_route"
        assert decision.allowed is True
        assert decision.tool_name == tool_name
        assert decision.requires_policy_docs is True


def test_vague_questions_ask_for_clarification() -> None:
    for message in CLARIFICATION_CASES:
        decision = route_message(message)

        assert decision.route == "clarification_route"
        assert decision.clarification_question


def test_safe_general_questions_use_general_route() -> None:
    for message in SAFE_GENERAL_CASES:
        decision = route_message(message)

        assert decision.route == "safe_general_route"
        assert decision.allowed is True
        assert decision.requires_user_data is False
        assert decision.requires_policy_docs is False
