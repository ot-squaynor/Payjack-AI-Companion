from __future__ import annotations

from dataclasses import dataclass


DISALLOWED_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "transaction_execution",
        ("send money", "transfer money", "pay bill", "withdraw cash", "top up"),
    ),
    (
        "financial_advice",
        ("what should i invest", "should i invest", "give me financial advice"),
    ),
    (
        "credit_decision",
        ("approve my loan", "am i eligible for credit", "credit score"),
    ),
    (
        "prompt_extraction",
        ("show me your prompt", "reveal the system prompt", "ignore previous instructions"),
    ),
)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    category: str | None = None
    message: str | None = None


def evaluate_input_policy(message: str) -> PolicyDecision:
    lowered = message.strip().lower()
    for category, patterns in DISALLOWED_PATTERNS:
        if any(pattern in lowered for pattern in patterns):
            return PolicyDecision(
                allowed=False,
                category=category,
                message=(
                    "I can help explain your financial activity and Payjack features, "
                    "but I cannot execute transactions, give financial advice, or bypass safety controls."
                ),
            )
    return PolicyDecision(allowed=True)


def evaluate_output_policy(message: str) -> PolicyDecision:
    return evaluate_input_policy(message)
