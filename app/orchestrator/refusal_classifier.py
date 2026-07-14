# app/orchestrator/refusal_classifier.py
# 2026-05-08
"""Refusal classifier module for determining if a user message should be refused based on its content. 
This module contains logic for analyzing user messages to identify requests that the PayJack AI Companion is not allowed to fulfill, such as 
requests for personalized financial advice, credit decisions, fraudulent activities, third-party data access, or attempts to extract or 
override system prompts. By classifying these refusal intents with associated confidence levels and reasons, the application can ensure that it 
responds appropriately to user messages that fall outside of its allowed capabilities while providing clear explanations for refusals when necessary."""

from __future__ import annotations

from dataclasses import dataclass
import re


INFORMATIONAL_PREFIXES = (
    "how do i",
    "how can i",
    "how would i",
    "how does",
    "can i",
    "can payjack",
    "does payjack",
    "explain",
    "what is",
    "what are",
    "what does",
    "what happens if",
    "what should i do if",
    "why",
    "where",
    "show me how",
    "guide me",
    "help me understand",
    "tell me about",
)

EXECUTION_VERBS = (
    "send",
    "transfer",
    "pay",
    "withdraw",
    "top up",
    "buy",
    "purchase",
    "sell",
    "open",
)

STARTS_WITH_EXECUTION_RE = re.compile(
    r"^(?:please\s+|kindly\s+|can you\s+|could you\s+|would you\s+)?"
    r"(?:send|transfer|pay|withdraw|top\s+up|buy|purchase|sell|open)\b"
)
ASSISTANT_EXECUTION_RE = re.compile(
    r"\b(?:can you|could you|would you|please|kindly|i want you to|go ahead and)\s+"
    r"(?:send|transfer|pay|withdraw|top\s+up|buy|purchase|sell|open)\b"
)
MONEY_MOVEMENT_CONTEXT_RE = re.compile(
    r"\b(?:send|transfer|pay|withdraw|top\s+up|buy|purchase|sell|open)\b.*"
    r"\b(?:now|for me|to\s+\w+|from\s+\w+|my funds|this investment|this product|this bill|cedis|ghs|\d+)\b"
)

FINANCIAL_ADVICE_PATTERNS = (
    re.compile(r"\bguarantee\b.*\b(?:profit|return|gain|outperform)\b"),
    re.compile(r"\b(?:definitely|certainly|guaranteed)\b.*\b(?:profit|outperform|return|gain)\b"),
    re.compile(r"\btell me exactly which\b.*\b(?:fund|investment|stock|product)\b.*\bbuy\b"),
    re.compile(r"\bwhich\b.*\b(?:fund|investment|stock|product)\b.*\b(?:should i buy|will definitely)\b"),
    re.compile(r"\bwhat should i invest\b"),
    re.compile(r"\bshould i\b.*\b(?:put all|invest all|move all)\b.*\b(?:savings|money|funds)\b"),
)

CREDIT_DECISION_PATTERNS = (
    re.compile(r"\bapprove\b.*\b(?:loan|credit)\b"),
    re.compile(r"\b(?:can i|will i)\b.*\bdefinitely\b.*\b(?:get|receive|qualify for)\b.*\b(?:credit|loan)\b"),
    re.compile(r"\bchange\b.*\bcredit score\b"),
    re.compile(r"\bmake me eligible\b"),
    re.compile(r"\bguarantee\b.*\b(?:loan|credit)\b"),
)

FRAUD_PATTERNS = (
    re.compile(r"\bbypass\b.*\b(?:kyc|verification|onboarding)\b"),
    re.compile(r"\bfake\b.*\b(?:kyc|verification|onboarding|identity|details)\b"),
    re.compile(r"\baccess\b.*\b(?:someone else|another user|another customer|friend)\b"),
    re.compile(r"\b(?:hide|delete|remove|alter|change)\b.*\b(?:transaction|record|history)\b"),
)

THIRD_PARTY_DATA_PATTERNS = (
    re.compile(r"\b(?:friend|wife|husband|brother|sister|someone else|another user|another customer)\b.*\b(?:balance|account|transaction|spending)\b"),
    re.compile(r"\b(?:show|pull|access)\b.*\b(?:another|someone else's|somebody else's)\b.*\b(?:account|balance|transaction)\b"),
    re.compile(r"\bbank account\b.*\b(?:not linked|not connected|outside payjack)\b"),
)

PROMPT_EXTRACTION_PATTERNS = (
    re.compile(r"\b(?:show|reveal|print|give me)\b.*\b(?:system prompt|developer message|hidden instructions|prompt)\b"),
    re.compile(r"\bignore\b.*\bprevious instructions\b"),
    re.compile(r"\boverride\b.*\b(?:policy|guardrails|instructions)\b"),
)

SENSITIVE_POLICY_CONTEXT_TERMS = (
    "payjack",
    "jackinvest",
    "policy",
    "policies",
    "help center",
    "help centre",
    "documentation",
    "docs",
    "kyc",
    "verification",
    "onboarding",
    "eligibility",
    "requirements",
    "credit",
    "loan",
    "fraud",
    "security",
    "privacy",
    "dispute",
    "chargeback",
    "failed transfer",
    "reversal",
    "risk",
    "risks",
)

UNSAFE_FRAUD_INSTRUCTION_RE = re.compile(
    r"\b(?:how\s+(?:do|can|would)\s+i|show\s+me\s+how|guide\s+me|help\s+me|tell\s+me\s+how|ways\s+to)\b"
    r".*\b(?:bypass|fake|hide|delete|remove|alter|change)\b"
)


@dataclass(frozen=True, slots=True)
class RefusalClassification:
    allowed: bool
    intent: str = "allowed"
    confidence: float = 0.0
    prohibited_reason: str | None = None


def _normalized_message(message: str) -> str:
    """Normalize the message by stripping leading/trailing whitespace, converting to lowercase, and collapsing multiple spaces into one."""
    return " ".join(message.strip().lower().split())


def _is_informational_request(lowered: str) -> bool:
    """Determine if the message is likely an informational request based on whether it starts with common informational prefixes."""
    return lowered.startswith(INFORMATIONAL_PREFIXES)


def _is_sensitive_policy_question(lowered: str) -> bool:
    """Determine if the message is likely asking about sensitive policies or PayJack-specific context 
    by checking for the presence of key terms in the message, but only if it appears to be an informational request."""
    return _is_informational_request(lowered) and any(
        term in lowered for term in SENSITIVE_POLICY_CONTEXT_TERMS
    )


def _blocked(
    *,
    intent: str,
    confidence: float,
    reason: str,
) -> RefusalClassification:
    """Helper function to create a RefusalClassification for blocked messages with a specific intent, confidence level, and reason."""
    return RefusalClassification(
        allowed=False,
        intent=intent,
        confidence=confidence,
        prohibited_reason=reason,
    )


def _matches_any_pattern(lowered: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(lowered) for pattern in patterns)


def _is_general_sensitive_policy_question(lowered: str) -> bool:
    return (
        _is_sensitive_policy_question(lowered)
        and " me " not in f" {lowered} "
        and " my " not in f" {lowered} "
    )


def _classify_fraud_request(
    lowered: str,
    *,
    is_sensitive_policy_question: bool,
) -> RefusalClassification | None:
    if not _matches_any_pattern(lowered, FRAUD_PATTERNS):
        return None
    if is_sensitive_policy_question and not UNSAFE_FRAUD_INSTRUCTION_RE.search(lowered):
        return RefusalClassification(allowed=True, confidence=0.78)
    return _blocked(
        intent="fraud_bypass_or_record_tampering",
        confidence=0.95,
        reason="The PayJack AI Companion cannot help bypass controls, fake details, or hide records.",
    )


def _classify_credit_decision_request(lowered: str) -> RefusalClassification | None:
    if not _matches_any_pattern(lowered, CREDIT_DECISION_PATTERNS):
        return None
    if _is_general_sensitive_policy_question(lowered):
        return RefusalClassification(allowed=True, confidence=0.78)
    return _blocked(
        intent="credit_approval_or_eligibility_decision",
        confidence=0.93,
        reason="The PayJack AI Companion cannot approve credit, guarantee eligibility, or alter credit decisions.",
    )


def _classify_execution_request(lowered: str) -> RefusalClassification | None:
    execution_requested = (
        STARTS_WITH_EXECUTION_RE.search(lowered)
        or ASSISTANT_EXECUTION_RE.search(lowered)
        or MONEY_MOVEMENT_CONTEXT_RE.search(lowered)
    )
    if _is_informational_request(lowered) or not execution_requested:
        return None
    return _blocked(
        intent="money_movement_or_account_execution",
        confidence=0.93,
        reason="The PayJack AI Companion is read-only and cannot execute transactions or open products.",
    )


def classify_refusal_intent(message: str) -> RefusalClassification:
    """Classify the refusal intent of a user message by checking it against various patterns that indicate prohibited requests.
    The function normalizes the message and then checks for patterns related to prompt extraction, third-party data access, fraud, 
    credit decisions, and financial advice.
    If a pattern is matched, it returns a RefusalClassification indicating that the request is not allowed, 
    along with the intent, confidence level, and reason for refusal.
    If no patterns are matched, it returns a RefusalClassification indicating that the request is allowed with a default confidence level."""
    lowered = _normalized_message(message)
    if not lowered:
        return RefusalClassification(allowed=True, confidence=0.0)

    is_sensitive_policy_question = _is_sensitive_policy_question(lowered)

    if _matches_any_pattern(lowered, PROMPT_EXTRACTION_PATTERNS):
        return _blocked(
            intent="prompt_extraction",
            confidence=0.96,
            reason="The PayJack AI Companion cannot reveal or override its system instructions.",
        )

    if _matches_any_pattern(lowered, THIRD_PARTY_DATA_PATTERNS):
        return _blocked(
            intent="third_party_private_data",
            confidence=0.94,
            reason="The PayJack AI Companion cannot access another person's private account data.",
        )

    fraud_classification = _classify_fraud_request(
        lowered,
        is_sensitive_policy_question=is_sensitive_policy_question,
    )
    if fraud_classification is not None:
        return fraud_classification

    credit_classification = _classify_credit_decision_request(lowered)
    if credit_classification is not None:
        return credit_classification

    if _matches_any_pattern(lowered, FINANCIAL_ADVICE_PATTERNS):
        return _blocked(
            intent="personalized_regulated_financial_advice",
            confidence=0.92,
            reason="The PayJack AI Companion cannot provide personalized regulated financial advice or guarantee returns.",
        )

    execution_classification = _classify_execution_request(lowered)
    if execution_classification is not None:
        return execution_classification

    return RefusalClassification(allowed=True, confidence=0.75)
