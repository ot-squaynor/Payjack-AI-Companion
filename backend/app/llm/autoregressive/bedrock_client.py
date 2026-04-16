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
        if request.tool_results:
            first_result = request.tool_results[0]
            tool_name = first_result.get("name")
            payload = first_result.get("result", {})

            if tool_name == "transaction_lookup":
                records = payload.get("records", [])
                if not records:
                    return "I could not find any transactions that match those filters."
                lines = ["Here are the latest matching transactions:"]
                for record in records[:5]:
                    lines.append(
                        "- {timestamp}: {merchant} {amount} {currency}".format(
                            timestamp=str(record.get("timestamp", ""))[:10],
                            merchant=record.get("merchant", "Unknown merchant"),
                            amount=record.get("amount", "0.00"),
                            currency=record.get("currency", ""),
                        )
                    )
                return "\n".join(lines)

            if tool_name == "spend_summary":
                grouped = payload.get("grouped_breakdown", [])
                total = payload.get("total_amount", "0.00")
                txn_count = payload.get("transaction_count", 0)
                lines = [f"Total spend for the selected filters is {total} across {txn_count} transactions."]
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

            if tool_name == "recurring_detection":
                records = payload.get("records", [])
                if not records:
                    return "I could not find any recurring payments that match those filters."
                lines = ["I found these recurring payment patterns:"]
                for row in records[:5]:
                    lines.append(
                        "- {merchant}: {cadence} at about {amount} {currency}".format(
                            merchant=row.get("merchant", "Unknown merchant"),
                            cadence=row.get("cadence", "unknown cadence"),
                            amount=row.get("average_amount", "0.00"),
                            currency=row.get("currency", ""),
                        )
                    )
                return "\n".join(lines)

        if request.grounding_mode == "rag" and request.citations:
            lines = ["Based on the accepted Payjack documentation, here are the most relevant details:"]
            for citation in request.citations[:2]:
                lines.append(
                    "- {title}: {snippet}".format(
                        title=citation.get("title", "Payjack documentation"),
                        snippet=citation.get("snippet", ""),
                    )
                )
            return "\n".join(lines)

        if request.grounding_mode == "base":
            if request.route == "rag":
                return (
                    "I could not verify that in reliable Payjack documentation, so I do not want to invent fees, "
                    "limits, policies, or app steps. Please check the relevant Payjack docs or try a more specific question."
                )
            return "I can help explain Payjack transactions and documentation, but I need more reliable context to answer that well."

        return "I can help with transaction lookups, spend summaries, recurring payments, and Payjack documentation."

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
            response = self.client.converse(
                modelId=selected_model.model_id,
                system=[{"text": request.system_prompt}],
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": request.prompt}],
                    }
                ],
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
