from app.security.policy_guard import evaluate_input_policy


def test_transaction_execution_intent_is_blocked() -> None:
    decision = evaluate_input_policy("Please transfer money from savings to checking.")

    assert decision.allowed is False
    assert decision.category == "money_movement_or_account_execution"
