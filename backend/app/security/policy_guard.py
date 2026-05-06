from __future__ import annotations

from dataclasses import dataclass

from app.orchestrator.refusal_classifier import classify_refusal_intent


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    category: str | None = None
    message: str | None = None
    confidence: float = 0.0


def evaluate_input_policy(message: str) -> PolicyDecision:
    refusal = classify_refusal_intent(message)
    if refusal.allowed:
        return PolicyDecision(allowed=True, confidence=refusal.confidence)
    return PolicyDecision(
        allowed=False,
        category=refusal.intent,
        message=refusal.prohibited_reason,
        confidence=refusal.confidence,
    )


def evaluate_output_policy(message: str) -> PolicyDecision:
    return evaluate_input_policy(message)
