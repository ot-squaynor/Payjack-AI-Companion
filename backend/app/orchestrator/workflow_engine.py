# app/orchestrator/workflow_engine.py
# 2026-04-16
"""Workflow engine module that orchestrates the end-to-end processing of a chat request, 
including input validation, intent routing, tool invocation, retrieval, prompt construction, 
LLM generation, output policy evaluation, and response formatting. 
This is the core module that ties together all the different components of the application to handle a chat request from start to finish."""

from __future__ import annotations

from dataclasses import dataclass
import time
import uuid

from app.api.schemas import ChatRequest, ChatResponse
from app.config import Settings
from app.errors import PolicyViolationError
from app.llm.autoregressive.bedrock_client import GenerationRequest
from app.llm.prompts.system_prompt import build_system_prompt
from app.orchestrator.context_builder import build_generation_prompt
from app.orchestrator.intent_router import route_message
from app.rag.retriever import RetrieverResult
from app.repository.processed_store import ProcessedStoreError
from app.orchestrator.response_formatter import format_chat_response
from app.security.audit_logging import log_audit_event
from app.security.auth_context import AuthContext
from app.security.parameter_validator import validate_chat_request
from app.security.pii_redaction import redact_value
from app.security.policy_guard import evaluate_input_policy, evaluate_output_policy
from app.telemetry.metrics import measure_duration
from app.tools.registry import ToolInvocation, ToolRegistry


def _resolve_grounding_mode(
    *,
    tool_traces: list[dict[str, object]],
    retrieval_result: RetrieverResult,
) -> str:
    if retrieval_result.usable_context and retrieval_result.citations:
        return "rag"
    if tool_traces:
        return "tool"
    return "base"


def _tool_data_unavailable_answer() -> str:
    return (
        "I can't access the local structured Payjack data needed for that request yet because the processed artifacts "
        "aren't ready. You can still ask about Payjack documentation, or rebuild the processed data and try again."
    )


@dataclass(slots=True)
class WorkflowEngine:
    settings: Settings
    tool_registry: ToolRegistry
    llm_client: object
    retriever: object | None = None # type is object to avoid circular import, should implement RetrieverProtocol

    def handle_chat(
        self,
        request: ChatRequest,
        *,
        auth_context: AuthContext,
    ) -> ChatResponse:
        request_id = request.client_request_id or f"req-{uuid.uuid4().hex[:12]}"
        session_id = request.session_id or f"session-{uuid.uuid4().hex[:12]}"
        started_at = time.perf_counter()

        validate_chat_request(
            message=request.message,
            session_id=session_id,
            max_message_chars=self.settings.max_message_chars,
        )

        policy_decision = evaluate_input_policy(request.message)
        if not policy_decision.allowed:
            refusal_payload = {
                "category": policy_decision.category or "policy_violation",
                "message": policy_decision.message or "I cannot help with that request.",
            }
            log_audit_event(
                event_type="refusal",
                request_id=request_id,
                auth_context=auth_context,
                payload=refusal_payload,
            )
            return format_chat_response(
                request_id=request_id,
                session_id=session_id,
                route="refuse",
                answer=refusal_payload["message"],
                tool_traces=[],
                citations=[],
                refusal=refusal_payload,
                debug={},
            )

        route_decision = route_message(request.message)
        tool_traces: list[dict[str, object]] = []
        citations: list[dict[str, object]] = []
        retrieval_result = RetrieverResult.empty(reason="retrieval_not_requested")
        retrieval_requested = route_decision.route in {"rag", "hybrid"}

        if route_decision.route in {"tool", "hybrid"} and route_decision.tool_name:
            try:
                tool_result = self.tool_registry.invoke(
                    ToolInvocation(
                        name=route_decision.tool_name,
                        arguments=route_decision.tool_arguments,
                    ),
                    auth_context=auth_context,
                )
            except ProcessedStoreError as exc:
                total_duration = measure_duration("chat_request", started_at)
                debug = {}
                if self.settings.enable_debug_traces:
                    debug = {
                        "reason": route_decision.reason,
                        "grounding_mode": "tool",
                        "tool_unavailable_reason": str(exc),
                        "duration_ms": total_duration.milliseconds,
                    }
                return format_chat_response(
                    request_id=request_id,
                    session_id=session_id,
                    route=route_decision.route,
                    answer=_tool_data_unavailable_answer(),
                    tool_traces=[],
                    citations=[],
                    debug=debug,
                )

            tool_traces.append(
                {
                    "name": tool_result.name,
                    "arguments": redact_value(tool_result.arguments),
                    "result": redact_value(tool_result.payload),
                    "warnings": list(tool_result.warnings),
                    "artifact_version": tool_result.artifact_version,
                }
            )

        if route_decision.route in {"rag", "hybrid"}:
            if self.retriever is None:
                retrieval_result = RetrieverResult.empty(reason="retriever_unavailable")
            else:
                retrieval_result = self.retriever.retrieve(request.message)
            if retrieval_result.usable_context:
                citations = [citation for citation in retrieval_result]

        if route_decision.route == "clarify":
            answer = (
                "I can help with transaction lookups, spend summaries, recurring payments, "
                "balances, and Payjack documentation. Please ask a more specific question."
            )
            return format_chat_response(
                request_id=request_id,
                session_id=session_id,
                route=route_decision.route,
                answer=answer,
                tool_traces=tool_traces,
                citations=citations,
                debug={"reason": route_decision.reason},
            )

        grounding_mode = _resolve_grounding_mode(
            tool_traces=tool_traces,
            retrieval_result=retrieval_result,
        )
        prompt = build_generation_prompt(
            user_message=request.message,
            tool_results=tool_traces,
            citations=citations,
            grounding_mode=grounding_mode,
        )
        generation = self.llm_client.generate(
            GenerationRequest(
                route=route_decision.route,
                user_message=request.message,
                system_prompt=build_system_prompt(route_decision.route, grounding_mode),
                prompt=prompt,
                grounding_mode=grounding_mode,
                tool_results=tool_traces,
                citations=citations,
            )
        )

        output_policy = evaluate_output_policy(generation.text)
        if not output_policy.allowed:
            raise PolicyViolationError(
                output_policy.message or "The model response violated a safety policy."
            )

        total_duration = measure_duration("chat_request", started_at)
        debug = {}
        if self.settings.enable_debug_traces:
            debug = {
                "reason": route_decision.reason,
                "grounding_mode": grounding_mode,
                "model_id": generation.model_id,
                "llm_request_id": generation.request_id,
                "usage": generation.usage,
                "estimated_cost_usd": generation.estimated_cost_usd,
                "duration_ms": total_duration.milliseconds,
            }
            if retrieval_requested:
                debug.update(
                    {
                        "retrieval_reason": retrieval_result.fallback_reason,
                        "retrieved_count": retrieval_result.retrieved_count,
                        "accepted_citation_count": retrieval_result.accepted_count,
                        "retrieval_top_score": retrieval_result.top_score,
                    }
                )

        log_audit_event(
            event_type="chat_response",
            request_id=request_id,
            auth_context=auth_context,
            payload={
                "route": route_decision.route,
                "reason": route_decision.reason,
                "tool_count": len(tool_traces),
                "citation_count": len(citations),
            },
        )

        return format_chat_response(
            request_id=request_id,
            session_id=session_id,
            route=route_decision.route,
            answer=generation.text,
            tool_traces=tool_traces,
            citations=citations,
            debug=debug,
        )
