from __future__ import annotations


MODEL_PRICING_PER_1K_TOKENS: dict[str, tuple[float, float]] = {
    "anthropic.claude-3-5-haiku-20241022-v1:0": (0.0008, 0.004),
}


def estimate_generation_cost(
    *,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    input_price, output_price = MODEL_PRICING_PER_1K_TOKENS.get(model_id, (0.0, 0.0))
    return round(
        ((input_tokens / 1000.0) * input_price) + ((output_tokens / 1000.0) * output_price),
        6,
    )
