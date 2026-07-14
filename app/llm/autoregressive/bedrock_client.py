# app/llm/autoregressive/bedrock_client.py
# 2026-04-02
"""Purpose: Define a client for invoking Bedrock models, along with a mock implementation for testing and development without incurring AWS costs."""

##BRICK 1: Imports and data models
from __future__ import annotations

from dataclasses import dataclass, field
import uuid
from typing import Any, Protocol

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings
from app.errors import ModelInvocationError
from app.llm.autoregressive.model_selector import select_model
from app.telemetry.cost_tracking import estimate_generation_cost

UNKNOWN_MERCHANT = "Unknown merchant"
DEFAULT_DOC_TITLE = "Payjack documentation"

##BRICK 2: Generation request and result models, and client protocol
@dataclass(frozen=True, slots=True)
class GenerationRequest:
    route: str
    user_message: str
    system_prompt: str
    prompt: str
    grounding_mode: str = "base"
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    conversation_history: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GenerationResult:
    text: str
    model_id: str
    request_id: str
    usage: dict[str, int] = field(default_factory=dict)
    estimated_cost_usd: float = 0.0


class GenerationClient(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResult:
        ...


##BRICK 3: Mock Bedrock client and deterministic summary builder
class MockBedrockClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, request: GenerationRequest) -> GenerationResult:
        request_id = f"mock-{uuid.uuid4().hex[:12]}"
        summary = self._build_summary(request)
        usage = {
            "input_tokens": max(1, len(request.prompt.split())),
            "output_tokens": max(1, len(summary.split())),
        }
        return GenerationResult(
            text=summary,
            model_id="mock-bedrock",
            request_id=request_id,
            usage=usage,
            estimated_cost_usd=0.0,
        )

    def _build_summary(self, request: GenerationRequest) -> str:
        tool_summary = self._build_tool_summary(request)
        if tool_summary is not None:
            return tool_summary

        rag_summary = self._build_rag_summary(request)
        if rag_summary is not None:
            return rag_summary

        if request.grounding_mode == "base":
            return self._build_base_summary(request)

        return "I can help with transaction lookups, spend summaries, recurring payments, and Payjack documentation."

    def _build_tool_summary(self, request: GenerationRequest) -> str | None:
        if not request.tool_results:
            return None

        first_result = request.tool_results[0]
        tool_name = first_result.get("name")
        payload = first_result.get("result", {})
        if tool_name == "fee_breakdown":
            return self._summarize_fee_breakdown(
                payload,
                has_citations=bool(request.citations),
            )

        handlers = {
            "transaction_lookup": self._summarize_transaction_lookup,
            "spend_summary": self._summarize_spend_summary,
            "recurring_detection": self._summarize_recurring_detection,
            "balances": self._summarize_balances,
            "status_explanation": self._summarize_status_explanation,
        }
        handler = handlers.get(str(tool_name))
        if handler is None:
            return None

        return handler(payload)

    def _summarize_transaction_lookup(self, payload: dict[str, Any]) -> str:
        records = payload.get("records", [])
        if not records:
            return "I could not find any transactions that match those filters."

        lines = ["Here are the latest matching transactions:"]
        for record in records[:5]:
            lines.append(
                "- {timestamp}: {merchant} {amount} {currency}".format(
                    timestamp=str(record.get("timestamp", ""))[:10],
                    merchant=record.get("merchant", UNKNOWN_MERCHANT),
                    amount=record.get("amount", "0.00"),
                    currency=record.get("currency", ""),
                )
            )
        return "\n".join(lines)

    def _summarize_spend_summary(self, payload: dict[str, Any]) -> str:
        grouped = payload.get("grouped_breakdown", [])
        total = payload.get("total_amount", "0.00")
        txn_count = payload.get("transaction_count", 0)
        lines = [
            f"Total spend for the selected filters is {total} across {txn_count} transactions."
        ]
        if grouped:
            lines.append("Top breakdown:")
            for row in grouped[:3]:
                lines.append(
                    "- {key}: {amount} ({count} transactions)".format(
                        key=row.get("key", "unknown"),
                        amount=row.get("total_amount", "0.00"),
                        count=row.get("transaction_count", 0),
                    )
                )
        return "\n".join(lines)

    def _summarize_recurring_detection(self, payload: dict[str, Any]) -> str:
        records = payload.get("records", [])
        if not records:
            return "I could not find any recurring payments that match those filters."

        lines = ["I found these recurring payment patterns:"]
        for row in records[:5]:
            lines.append(
                "- {merchant}: {cadence} at about {amount} {currency}".format(
                    merchant=row.get("merchant", UNKNOWN_MERCHANT),
                    cadence=row.get("cadence", "unknown cadence"),
                    amount=row.get("average_amount", "0.00"),
                    currency=row.get("currency", ""),
                )
            )
        return "\n".join(lines)

    def _summarize_balances(self, payload: dict[str, Any]) -> str:
        records = payload.get("records", [])
        if not records:
            return "I could not find any balances for the selected account scope."

        lines = ["Here are the available account balances:"]
        for record in records[:5]:
            lines.append(
                "- {name}: {available} {currency} available".format(
                    name=record.get("account_name") or record.get("account_id", "Account"),
                    available=record.get(
                        "available_balance",
                        record.get("current_balance", "unknown"),
                    ),
                    currency=record.get("currency", ""),
                )
            )
        return "\n".join(lines)

    def _summarize_status_explanation(self, payload: dict[str, Any]) -> str:
        counts = payload.get("counts_by_status", {})
        if not counts:
            return "I could not find transaction status information for that scope."

        lines = ["Here is the transaction status breakdown:"]
        for status, count in counts.items():
            lines.append(f"- {status}: {count}")
        return "\n".join(lines)

    def _summarize_fee_breakdown(
        self,
        payload: dict[str, Any],
        *,
        has_citations: bool,
    ) -> str:
        records = payload.get("records", [])
        total = payload.get("total_amount", "0.00")
        if not records:
            return "I could not find fee-like transactions that match those filters."

        lines = [
            (
                f"I found {len(records)} fee-like transaction(s), "
                f"totaling {total} across the selected filters:"
            )
        ]
        for record in records[:5]:
            lines.append(
                "- {timestamp}: {merchant} {amount} {currency} ({reason})".format(
                    timestamp=str(record.get("timestamp", ""))[:10],
                    merchant=record.get("merchant", UNKNOWN_MERCHANT),
                    amount=record.get("amount", "0.00"),
                    currency=record.get("currency", ""),
                    reason=record.get("matched_reason", "fee match"),
                )
            )
        if has_citations:
            lines.append(
                "I can also use the accepted Payjack documentation to explain the policy context."
            )
        return "\n".join(lines)

    def _build_rag_summary(self, request: GenerationRequest) -> str | None:
        if request.grounding_mode not in {"rag", "hybrid"} or not request.citations:
            return None

        lines = [
            "Based on the accepted Payjack documentation, here are the most relevant details:"
        ]
        for citation in request.citations[:2]:
            lines.append(
                "- {title}: {snippet}".format(
                    title=citation.get("title", DEFAULT_DOC_TITLE),
                    snippet=citation.get("snippet", ""),
                )
            )
        return "\n".join(lines)

    def _build_base_summary(self, request: GenerationRequest) -> str:
        if request.route == "safe_general_route":
            return (
                "Here is a general explanation: this request does not need private Payjack data, so I can answer from general knowledge. "
                "For Payjack-specific rules or current account details, I would need grounded documentation or read-only account context."
            )
        if request.route in {"rag", "rag_route"}:
            return (
                "I could not verify that in reliable Payjack documentation, so I do not want to invent fees, "
                "limits, policies, or app steps. Please check the relevant Payjack docs or try a more specific question."
            )
        return "I can help explain Payjack transactions and documentation, but I need more reliable context to answer that well."

##BRICK 4: Bedrock runtime client and real model invocation
class BedrockRuntimeClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
            config=BotoConfig(
                read_timeout=settings.bedrock_timeout_seconds,
                connect_timeout=settings.bedrock_timeout_seconds,
                retries={"max_attempts": 2},
            ),
        )

    def generate(self, request: GenerationRequest) -> GenerationResult:
        selected_model = select_model(route=request.route, settings=self.settings)
        request_id = f"bedrock-{uuid.uuid4().hex[:12]}"
        try:
            history_messages = [
                {"role": turn["role"], "content": [{"text": turn["content"]}]}
                for turn in request.conversation_history
            ]
            messages = history_messages + [
                {"role": "user", "content": [{"text": request.prompt}]}
            ]
            response = self.client.converse(
                modelId=selected_model.model_id,
                system=[{"text": request.system_prompt}],
                messages=messages,
            )
        except (BotoCoreError, ClientError) as exc:
            raise ModelInvocationError(
                "Failed to generate a Bedrock response.",
                detail=str(exc),
            ) from exc

        output_message = response.get("output", {}).get("message", {})
        content_blocks = output_message.get("content", [])
        text = " ".join(
            block.get("text", "")
            for block in content_blocks
            if isinstance(block, dict)
        ).strip()
        usage = response.get("usage", {})
        input_tokens = int(usage.get("inputTokens", 0))
        output_tokens = int(usage.get("outputTokens", 0))
        return GenerationResult(
            text=text or "I was unable to generate a response.",
            model_id=selected_model.model_id,
            request_id=request_id,
            usage={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
            estimated_cost_usd=estimate_generation_cost(
                model_id=selected_model.model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
        )

##BRICK 5: Generation client factory
def build_generation_client(settings: Settings) -> GenerationClient: # pragma: no cover - tested indirectly through chat endpoint integration tests
    if settings.use_mock_bedrock:
        return MockBedrockClient(settings)
    return BedrockRuntimeClient(settings)
