from app.orchestrator.intent_router import route_message


def test_routes_transaction_lookup_for_last_n_transactions() -> None:
    decision = route_message("Show my last 3 transactions")

    assert decision.route == "tool"
    assert decision.tool_name == "transaction_lookup"
    assert decision.tool_arguments["limit"] == 3


def test_routes_spend_summary_with_category_and_date_filters() -> None:
    decision = route_message("How much did I spend on groceries last month?")

    assert decision.route == "tool"
    assert decision.tool_name == "spend_summary"
    assert decision.tool_arguments["categories"] == ("groceries",)
    assert "start_date" in decision.tool_arguments
    assert "end_date" in decision.tool_arguments


def test_routes_documentation_queries_to_rag() -> None:
    decision = route_message("What is the Payjack fee policy?")

    assert decision.route == "rag"
    assert decision.tool_name is None


def test_routes_transaction_date_ranges_to_lookup_tool() -> None:
    decision = route_message("Look up my transactions from April to May")

    assert decision.route == "tool"
    assert decision.tool_name == "transaction_lookup"
    assert "start_date" in decision.tool_arguments
    assert "end_date" in decision.tool_arguments


def test_returns_clarify_when_no_confident_route_exists() -> None:
    decision = route_message("Tell me something interesting")

    assert decision.route == "clarify"
