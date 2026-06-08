# app/orchestrator/response_planner.py
# 2026-05-08
"""Response planner module for constructing static response plans based on intent classification decisions. 
This module contains logic for building static response plans that can be returned directly to the user without LLM generation based on the 
classified intent of their message. For example, if a user's message is classified as a refusal intent, this module can generate a static response 
plan that includes an appropriate refusal message and any safe redirection guidance. If a user's message is classified as needing clarification, 
this module can generate a static response plan that includes a clarification question to ask the user. By centralizing this logic in one place, 
we can ensure consistency in how static responses are generated across different parts of the application and make it easier to maintain and update 
the response planning process as needed."""

#IMPORTS
from __future__ import annotations

from dataclasses import dataclass

from app.orchestrator.intent_router import RouteDecision


@dataclass(frozen=True, slots=True)
class StaticResponsePlan:
    answer: str
    refusal: dict[str, str] | None = None


SAFE_REDIRECTS: dict[str, str] = {
    "money_movement_or_account_execution": (
        "I can still explain the relevant app steps or help you review read-only transaction details."
    ),
    "personalized_regulated_financial_advice": (
        "I can explain products, fees, risks, and general considerations, or suggest speaking with a qualified advisor."
    ),
    "credit_approval_or_eligibility_decision": (
        "I can explain general eligibility factors where documentation is available."
    ),
    "fraud_bypass_or_record_tampering": (
        "I can help with legitimate onboarding, security, or transaction-support questions."
    ),
    "third_party_private_data": (
        "I can only help with data that is available in the authenticated PayJack context."
    ),
    "prompt_extraction": (
        "I can still help with PayJack questions, read-only financial analysis, or general safe explanations."
    ),
}


def build_refusal_plan(decision: RouteDecision) -> StaticResponsePlan:
    """Constructs a StaticResponsePlan for refusal intents based on the provided RouteDecision. 
    This function takes the classified intent and any associated prohibited reason from the RouteDecision and constructs a refusal message 
    that explains why the request cannot be fulfilled. It also includes safe redirection guidance based on the specific intent, 
    using predefined messages from the SAFE_REDIRECTS dictionary. The resulting StaticResponsePlan includes both the refusal message 
    and any relevant redirection guidance, providing a clear and informative response to the user while ensuring that the system's limitations 
    and policies are communicated effectively."""
    reason = decision.prohibited_reason or "I cannot help with that request."
    redirect = SAFE_REDIRECTS.get(
        decision.intent,
        "I can redirect to safe, read-only guidance instead.",
    )
    answer = f"{reason} {redirect}"
    return StaticResponsePlan(
        answer=answer,
        refusal={
            "category": decision.intent,
            "message": answer,
        },
    )


def build_clarification_plan(decision: RouteDecision) -> StaticResponsePlan:
    question = decision.clarification_question or (
        "What would you like me to check: transactions, spending, balances, PayJack documentation, or a general question?"
    )
    return StaticResponsePlan(answer=question)


def plan_static_response(decision: RouteDecision) -> StaticResponsePlan | None:
    if decision.route == "refusal_route":
        return build_refusal_plan(decision)
    if decision.route == "clarification_route":
        return build_clarification_plan(decision)
    return None
