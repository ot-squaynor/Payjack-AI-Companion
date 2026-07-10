from app.config import Settings
from app.llm.autoregressive.bedrock_client import GenerationRequest, MockBedrockClient


def test_mock_bedrock_client_returns_normalized_generation_contract(configured_test_env) -> None:
    client = MockBedrockClient(Settings.from_env())

    result = client.generate(
        GenerationRequest(
            route="tool",
            user_message="Show my last transactions",
            system_prompt="You are the Payjack AI Compainion.",
            prompt="Summarize the latest transactions.",
            grounding_mode="tool",
            tool_results=[
                {
                    "name": "transaction_lookup",
                    "result": {
                        "records": [
                            {
                                "timestamp": "2026-03-28T10:00:00Z",
                                "merchant": "Fresh Market",
                                "amount": "45.50",
                                "currency": "GHS",
                            }
                        ]
                    },
                }
            ],
        )
    )

    assert result.model_id == "mock-bedrock"
    assert result.request_id.startswith("mock-")
    assert result.usage["input_tokens"] > 0
    assert result.usage["output_tokens"] > 0


def test_mock_bedrock_client_uses_base_fallback_when_grounding_is_unusable(configured_test_env) -> None:
    client = MockBedrockClient(Settings.from_env())

    result = client.generate(
        GenerationRequest(
            route="rag",
            user_message="What are the Payjack fees and limits?",
            system_prompt="You are the Payjack AI Companion.",
            prompt="Answer carefully without documentation.",
            grounding_mode="base",
            citations=[],
        )
    )

    assert "could not verify" in result.text
    assert "documentation" in result.text.lower()
