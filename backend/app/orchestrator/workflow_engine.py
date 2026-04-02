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
from app.orchestrator.response_formatter import format_chat_response
from app.security.audit_logging import log_audit_event
from app.security.auth_context import AuthContext
from app.security.parameter_validator import validate_chat_request
from app.security.pii_redaction import redact_value
from app.security.policy_guard import evaluate_input_policy, evaluate_output_policy
from app.telemetry.metrics import measure_duration
from app.tools.registry import ToolInvocation, ToolRegistry


@dataclass(slots=True)
class WorkflowEngine:
    settings: Settings
    tool_registry: ToolRegistry
    llm_client: object
    retriever: object | None = None

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

        if route_decision.route in {"tool", "hybrid"} and route_decision.tool_name:
            tool_result = self.tool_registry.invoke(
                ToolInvocation(
                    name=route_decision.tool_name,
                    arguments=route_decision.tool_arguments,
                ),
                auth_context=auth_context,
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

        if route_decision.route in {"rag", "hybrid"} and self.retriever is not None:
            retrieval_result = self.retriever.retrieve(request.message)
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

        prompt = build_generation_prompt(
            user_message=request.message,
            tool_results=tool_traces,
            citations=citations,
        )
        generation = self.llm_client.generate(
            GenerationRequest(
                route=route_decision.route,
                user_message=request.message,
                system_prompt=build_system_prompt(route_decision.route),
                prompt=prompt,
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
                "model_id": generation.model_id,
                "llm_request_id": generation.request_id,
                "usage": generation.usage,
                "estimated_cost_usd": generation.estimated_cost_usd,
                "duration_ms": total_duration.milliseconds,
            }

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
