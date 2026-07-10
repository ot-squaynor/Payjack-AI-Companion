from app.config import Settings
from app.llm.autoregressive.bedrock_client import GenerationRequest, MockBedrockClient


def test_mock_bedrock_summary_preserves_tool_numbers(configured_test_env) -> None:
    client = MockBedrockClient(Settings.from_env())

    result = client.generate(
        GenerationRequest(
            route="tool",
            user_message="How much did I spend?",
            system_prompt="You are Payjack.",
            prompt="Summarize spend totals.",
            grounding_mode="tool",
            tool_results=[
                {
                    "name": "spend_summary",
                    "result": {
                        "total_amount": "70.50",
                        "transaction_count": 2,
                        "grouped_breakdown": [
                            {"key": "groceries", "total_amount": "45.50", "transaction_count": 1},
                            {"key": "transport", "total_amount": "25.00", "transaction_count": 1},
                        ],
                    },
                }
            ],
        )
    )

    assert "70.50" in result.text
    assert "45.50" in result.text
