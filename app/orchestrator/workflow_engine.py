# app/orchestrator/workflow_engine.py
# 2026-04-16
"""Workflow engine module that orchestrates the end-to-end processing of a chat request, 
including input validation, intent routing, tool invocation, retrieval, prompt construction, 
LLM generation, output policy evaluation, and response formatting. 
This is the core module that ties together all the different components of the application to handle a chat request from start to finish."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import time
import uuid

from app.api.schemas import ChatRequest, ChatResponse
from app.chat_history.store import ChatHistoryError, ChatHistoryStore
from app.config import Settings
from app.errors import PolicyViolationError
from app.llm.autoregressive.bedrock_client import GenerationRequest
from app.llm.prompts.system_prompt import build_system_prompt
from app.memory.session_memory import (
    InMemorySessionMemoryStore,
    ToolMemoryFact,
    resolve_contextual_followup,
)
from app.orchestrator.context_builder import build_generation_prompt
from app.orchestrator.intent_router import route_message
from app.rag.retriever import RetrieverResult
from app.repository.processed_store import ProcessedStoreError
from app.orchestrator.response_formatter import format_chat_response
from app.orchestrator.response_planner import plan_static_response
from app.security.audit_logging import log_audit_event
from app.security.auth_context import AuthContext
from app.security.parameter_validator import validate_chat_request
from app.security.pii_redaction import redact_value
from app.security.policy_guard import evaluate_output_policy
from app.telemetry.metrics import measure_duration
from app.tools.registry import ToolInvocation, ToolRegistry


logger = logging.getLogger(__name__)


def _resolve_grounding_mode(
    *,
    tool_traces: list[dict[str, object]],
    retrieval_result: RetrieverResult,
) -> str:
    if tool_traces and retrieval_result.usable_context and retrieval_result.citations:
        return "hybrid"
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
    session_memory: InMemorySessionMemoryStore = field(default_factory=InMemorySessionMemoryStore)
    chat_history_store: ChatHistoryStore | None = None

    def _remember_response(
        self,
        *,
        response: ChatResponse,
        user_message: str,
        tool_facts: list[ToolMemoryFact] | None = None,
        auth_context: AuthContext | None = None,
    ) -> ChatResponse:
        """Records the exchange of a user message and assistant response into the session memory, including any tool facts and citations,
        and returns the original response. This function takes the structured ChatResponse object,
        extracts the relevant information such as the session ID, request ID, route, and answer,
        and combines it with the original user message and any tool facts to create a comprehensive record of the interaction.
        The tool facts are stored in a structured format that includes the name of the tool, its arguments, results,
        and any artifact version information. Additionally, any citations included in the response are also recorded in the session memory.
        This allows for a complete history of the conversation to be maintained, which can be useful for future context retrieval and analysis."""
        self.session_memory.record_exchange(
            session_id=response.session_id,
            user_message=user_message,
            assistant_answer=response.answer,
            request_id=response.request_id,
            route=response.route,
            tool_facts=tool_facts or [],
            citations=[citation.model_dump() for citation in response.citations],
        )

        if self.chat_history_store is not None and auth_context is not None:
            try:
                self.chat_history_store.append_message(
                    session_id=response.session_id,
                    auth_context=auth_context,
                    role="user",
                    content=user_message,
                )
                self.chat_history_store.append_message(
                    session_id=response.session_id,
                    auth_context=auth_context,
                    role="assistant",
                    content=response.answer,
                    request_id=response.request_id,
                    route=response.route,
                    tool_traces=[trace.model_dump() for trace in response.tool_traces],
                    citations=[citation.model_dump() for citation in response.citations],
                    refusal=response.refusal.model_dump() if response.refusal else None,
                    debug={
                        "grounding_mode": response.debug.get("grounding_mode"),
                        "duration_ms": response.debug.get("duration_ms"),
                    },
                )
            except ChatHistoryError:
                logger.warning(
                    "Failed to persist chat history for session %s; continuing without durable history.",
                    response.session_id,
                    exc_info=True,
                )

        return response

    def handle_chat(
        self,
        request: ChatRequest,
        *,
        auth_context: AuthContext,
    ) -> ChatResponse:
        """Handles a chat request by orchestrating the entire workflow from input validation to response generation and formatting.
        This function serves as the main entry point for processing a chat request. It begins by validating the input message and ensuring 
        it meets the defined constraints.
        It then checks for any relevant contextual follow-ups based on the session memory, which allows the system to maintain continuity 
        in the conversation.
        If no contextual follow-up is found, it proceeds to route the message to determine the appropriate processing path, 
        which may include static responses or tool invocations.
        If tool invocations are required, it executes them and collects their results, while also handling any potential errors 
        that may arise during tool execution.
        If retrieval of external context is needed, it performs the retrieval and incorporates any relevant citations into the response.
        Finally, it constructs the prompt for the language model, generates the response, evaluates it against output policies, 
        and formats the final response to be returned to the client.
        Throughout the process, it also logs relevant audit events and measures the duration of the request handling for monitoring and 
        debugging purposes."""
        request_id = request.client_request_id or f"req-{uuid.uuid4().hex[:12]}"
        session_id = request.session_id or f"session-{uuid.uuid4().hex[:12]}"
        started_at = time.perf_counter()

        if self.chat_history_store is not None:
            try:
                self.chat_history_store.get_or_create_session(
                    session_id=session_id, auth_context=auth_context
                )
            except ChatHistoryError:
                logger.warning(
                    "Failed to get-or-create durable chat session %s; continuing without durable history.",
                    session_id,
                    exc_info=True,
                )

        validate_chat_request(
            message=request.message,
            session_id=session_id,
            max_message_chars=self.settings.max_message_chars,
        )

        memory_snapshot = self.session_memory.get(session_id)
        memory_followup = resolve_contextual_followup(request.message, memory_snapshot)
        if memory_followup is not None:
            total_duration = measure_duration("chat_request", started_at)
            debug = {}
            if self.settings.enable_debug_traces:
                debug = {
                    "memory_context": memory_followup.to_debug_dict(),
                    "duration_ms": total_duration.milliseconds,
                }
            response = format_chat_response(
                request_id=request_id,
                session_id=session_id,
                route=memory_followup.route,
                answer=memory_followup.answer,
                tool_traces=[],
                citations=[],
                debug=debug,
            )
            log_audit_event(
                event_type="chat_response",
                request_id=request_id,
                auth_context=auth_context,
                payload={
                    "route": memory_followup.route,
                    "intent": "contextual_followup",
                    "confidence": memory_followup.confidence,
                    "allowed": True,
                    "refusal_reason": None,
                    "duration_ms": total_duration.milliseconds,
                    "tool_count": 0,
                    "citation_count": 0,
                    "memory_source_request_id": memory_followup.source_request_id,
                },
            )
            return self._remember_response(
                response=response,
                user_message=request.message,
                auth_context=auth_context,
            )

        route_decision = route_message(request.message)
        tool_traces: list[dict[str, object]] = []
        memory_tool_facts: list[ToolMemoryFact] = []
        citations: list[dict[str, object]] = []
        retrieval_result = RetrieverResult.empty(reason="retrieval_not_requested")
        retrieval_requested = route_decision.requires_policy_docs

        static_plan = plan_static_response(route_decision)
        if static_plan is not None:
            total_duration = measure_duration("chat_request", started_at)
            debug = {}
            if self.settings.enable_debug_traces:
                debug = {
                    "route_decision": route_decision.to_debug_dict(),
                    "duration_ms": total_duration.milliseconds,
                }
            log_audit_event(
                event_type="refusal" if route_decision.route == "refusal_route" else "chat_response",
                request_id=request_id,
                auth_context=auth_context,
                payload={
                    "route": route_decision.route,
                    "intent": route_decision.intent,
                    "confidence": route_decision.confidence,
                    "allowed": route_decision.allowed,
                    "refusal_reason": route_decision.prohibited_reason,
                    "duration_ms": total_duration.milliseconds,
                    "tool_count": 0,
                    "citation_count": 0,
                },
            )
            response = format_chat_response(
                request_id=request_id,
                session_id=session_id,
                route=route_decision.route,
                answer=static_plan.answer,
                tool_traces=[],
                citations=[],
                refusal=static_plan.refusal,
                debug=debug,
            )
            return self._remember_response(
                response=response,
                user_message=request.message,
                auth_context=auth_context,
            )

        if route_decision.tool_invocations:
            try:
                for tool_plan in route_decision.tool_invocations:
                    tool_result = self.tool_registry.invoke(
                        ToolInvocation(
                            name=tool_plan.name,
                            arguments=dict(tool_plan.arguments),
                        ),
                        auth_context=auth_context,
                    )
                    memory_tool_facts.append(
                        ToolMemoryFact(
                            name=tool_result.name,
                            arguments=dict(tool_result.arguments),
                            result=dict(tool_result.payload),
                            artifact_version=tool_result.artifact_version,
                        )
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
            except ProcessedStoreError as exc:
                total_duration = measure_duration("chat_request", started_at)
                debug = {}
                if self.settings.enable_debug_traces:
                    debug = {
                        "route_decision": route_decision.to_debug_dict(),
                        "grounding_mode": "tool",
                        "tool_unavailable_reason": str(exc),
                        "duration_ms": total_duration.milliseconds,
                    }
                response = format_chat_response(
                    request_id=request_id,
                    session_id=session_id,
                    route=route_decision.route,
                    answer=_tool_data_unavailable_answer(),
                    tool_traces=[],
                    citations=[],
                    debug=debug,
                )
                return self._remember_response(
                    response=response,
                    user_message=request.message,
                    auth_context=auth_context,
                )

        if retrieval_requested:
            if self.retriever is None:
                retrieval_result = RetrieverResult.empty(reason="retriever_unavailable")
            else:
                retrieval_result = self.retriever.retrieve(request.message)
            if retrieval_result.usable_context:
                citations = [citation for citation in retrieval_result]

        grounding_mode = _resolve_grounding_mode(
            tool_traces=tool_traces,
            retrieval_result=retrieval_result,
        )
        prompt = build_generation_prompt(
            user_message=request.message,
            route=route_decision.route,
            tool_results=tool_traces,
            citations=citations,
            grounding_mode=grounding_mode,
        )
        conversation_history = [
            {"role": t.role, "content": t.content}
            for t in memory_snapshot.turns
        ]
        generation = self.llm_client.generate(
            GenerationRequest(
                route=route_decision.route,
                user_message=request.message,
                system_prompt=build_system_prompt(route_decision.route, grounding_mode),
                prompt=prompt,
                grounding_mode=grounding_mode,
                tool_results=tool_traces,
                citations=citations,
                conversation_history=conversation_history,
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
                "route_decision": route_decision.to_debug_dict(),
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
                "intent": route_decision.intent,
                "confidence": route_decision.confidence,
                "allowed": route_decision.allowed,
                "refusal_reason": route_decision.prohibited_reason,
                "duration_ms": total_duration.milliseconds,
                "tool_count": len(tool_traces),
                "citation_count": len(citations),
            },
        )

        response = format_chat_response(
            request_id=request_id,
            session_id=session_id,
            route=route_decision.route,
            answer=generation.text,
            tool_traces=tool_traces,
            citations=citations,
            debug=debug,
        )
        return self._remember_response(
            response=response,
            user_message=request.message,
            tool_facts=memory_tool_facts,
            auth_context=auth_context,
        )
