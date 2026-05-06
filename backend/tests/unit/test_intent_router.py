from app.orchestrator.intent_router import route_message


def test_routes_transaction_lookup_for_last_n_transactions() -> None:
    decision = route_message("Show my last 3 transactions")

    assert decision.route == "deterministic_tool_route"
    assert decision.tool_name == "transaction_lookup"
    assert decision.tool_arguments["limit"] == 3
    assert decision.allowed is True


def test_routes_spend_summary_with_category_and_date_filters() -> None:
    decision = route_message("How much did I spend on groceries last month?")

    assert decision.route == "deterministic_tool_route"
    assert decision.tool_name == "spend_summary"
    assert decision.tool_arguments["categories"] == ("groceries",)
    assert "start_date" in decision.tool_arguments
    assert "end_date" in decision.tool_arguments


def test_routes_recurring_payment_amount_threshold() -> None:
    decision = route_message("Show me all recurring payments above 50 cedis on my account")

    assert decision.route == "deterministic_tool_route"
    assert decision.tool_name == "recurring_detection"
    assert decision.tool_arguments["min_average_amount"] == "50"


def test_routes_documentation_queries_to_rag() -> None:
    decision = route_message("What is the Payjack fee policy?")

    assert decision.route == "rag_route"
    assert decision.tool_name is None
    assert decision.requires_policy_docs is True


def test_routes_transaction_date_ranges_to_lookup_tool() -> None:
    decision = route_message("Look up my transactions from April to May")

    assert decision.route == "deterministic_tool_route"
    assert decision.tool_name == "transaction_lookup"
    assert "start_date" in decision.tool_arguments
    assert "end_date" in decision.tool_arguments


def test_routes_safe_general_questions_without_payjack_scope() -> None:
    decision = route_message("Tell me something interesting about budgeting")

    assert decision.route == "safe_general_route"
    assert decision.allowed is True


def test_routes_vague_requests_to_clarification() -> None:
    decision = route_message("Can you check it?")

    assert decision.route == "clarification_route"
    assert decision.clarification_question


def test_routes_fee_transaction_questions_to_hybrid() -> None:
    decision = route_message("Why was I charged this fee?")

    assert decision.route == "hybrid_route"
    assert decision.tool_name == "fee_breakdown"
    assert decision.requires_policy_docs is True


def test_routes_execution_requests_to_refusal() -> None:
    decision = route_message("Transfer 500 cedis now.")

    assert decision.route == "refusal_route"
    assert decision.allowed is False
    assert decision.intent == "money_movement_or_account_execution"
