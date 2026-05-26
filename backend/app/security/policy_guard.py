from __future__ import annotations

from dataclasses import dataclass
import re

from app.orchestrator.refusal_classifier import classify_refusal_intent


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    category: str | None = None
    message: str | None = None
    confidence: float = 0.0


OUTPUT_PROMPT_EXTRACTION_PATTERNS = (
    re.compile(r"\bignore\b.*\bprevious instructions\b"),
    re.compile(r"\boverride\b.*\b(?:policy|guardrails|instructions)\b"),
    re.compile(r"\b(?:here is|here's|below is|these are)\b.*\b(?:system prompt|developer message|hidden instructions)\b"),
)

OUTPUT_ASSISTANT_EXECUTION_RE = re.compile(
    r"\b(?:i|we)\s+(?:can|will|would|am going to|are going to|just|have|successfully)?\s*"
    r"(?:send|sent|transfer|transferred|pay|paid|withdraw|withdrew|top\s+up|buy|bought|purchase|purchased|sell|sold|open|opened)\b"
)

OUTPUT_FRAUD_INSTRUCTION_RE = re.compile(
    r"\b(?:to|you can|steps? to|here'?s how to)\b.*\b(?:bypass kyc|fake verification|hide transaction|delete transaction|alter transaction)\b"
)


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
    lowered = " ".join(message.strip().lower().split())
    if not lowered:
        return PolicyDecision(allowed=True, confidence=0.0)

    if any(pattern.search(lowered) for pattern in OUTPUT_PROMPT_EXTRACTION_PATTERNS):
        return PolicyDecision(
            allowed=False,
            category="prompt_extraction",
            message="The PayJack AI Companion cannot reveal or override its system instructions.",
            confidence=0.96,
        )

    if OUTPUT_FRAUD_INSTRUCTION_RE.search(lowered):
        return PolicyDecision(
            allowed=False,
            category="fraud_bypass_or_record_tampering",
            message="The PayJack AI Companion cannot help bypass controls, fake details, or hide records.",
            confidence=0.95,
        )

    if OUTPUT_ASSISTANT_EXECUTION_RE.search(lowered):
        return PolicyDecision(
            allowed=False,
            category="money_movement_or_account_execution",
            message="The PayJack AI Companion is read-only and cannot execute transactions or open products.",
            confidence=0.93,
        )

    return PolicyDecision(allowed=True, confidence=0.75)
