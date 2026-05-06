from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.orchestrator.intent_classifier import ToolPlan, classify_intent
from app.orchestrator.refusal_classifier import classify_refusal_intent


@dataclass(frozen=True, slots=True)
class RouteDecision:
    route: str
    intent: str
    confidence: float
    requires_user_data: bool
    requires_policy_docs: bool
    is_read_only: bool
    allowed: bool
    prohibited_reason: str | None = None
    clarification_question: str | None = None
    tool_invocations: tuple[ToolPlan, ...] = ()
    reason: str = "intent_policy_decision"

    @property
    def tool_name(self) -> str | None:
        if not self.tool_invocations:
            return None
        return self.tool_invocations[0].name

    @property
    def tool_arguments(self) -> dict[str, object]:
        if not self.tool_invocations:
            return {}
        return dict(self.tool_invocations[0].arguments)

    def to_debug_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "intent": self.intent,
            "confidence": self.confidence,
            "requires_user_data": self.requires_user_data,
            "requires_policy_docs": self.requires_policy_docs,
            "is_read_only": self.is_read_only,
            "allowed": self.allowed,
            "prohibited_reason": self.prohibited_reason,
            "clarification_question": self.clarification_question,
            "tools": [
                {"name": invocation.name, "arguments": dict(invocation.arguments)}
                for invocation in self.tool_invocations
            ],
            "reason": self.reason,
        }


def route_message(message: str) -> RouteDecision:
    refusal = classify_refusal_intent(message)
    if not refusal.allowed:
        return RouteDecision(
            route="refusal_route",
            intent=refusal.intent,
            confidence=refusal.confidence,
            requires_user_data=False,
            requires_policy_docs=False,
            is_read_only=False,
            allowed=False,
            prohibited_reason=refusal.prohibited_reason,
            reason="prohibited_intent",
        )

    intent = classify_intent(message)
    return RouteDecision(
        route=intent.route,
        intent=intent.intent,
        confidence=intent.confidence,
        requires_user_data=intent.requires_user_data,
        requires_policy_docs=intent.requires_policy_docs,
        is_read_only=intent.is_read_only,
        allowed=True,
        prohibited_reason=None,
        clarification_question=intent.clarification_question,
        tool_invocations=intent.tool_plans,
        reason="allowed_intent",
    )
