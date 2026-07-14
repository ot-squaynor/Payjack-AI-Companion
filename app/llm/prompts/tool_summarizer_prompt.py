# app/llm/prompts/tool_summarizer_prompt.py
# 2026-04-16
"""Prompt construction for summarizing tool results and retrieved context to send to the LLM for generation. 
This module is responsible for building the prompt that will be sent to the LLM for generation, based on the user message, tool results, 
and retrieved context. It encapsulates the logic for how to combine these different sources of information into a coherent prompt that the LLM 
can understand and use to generate a response. By centralizing this logic in one place, we can ensure consistency across different parts of the 
application and make it easier to maintain and update the prompt construction process as needed."""

from __future__ import annotations

import json
from typing import Any

COMPANION_ANSWER_INSTRUCTION = "Answer as the Payjack AI Financial Companion."
ACCEPTED_DOCS_SECTION = "Accepted Payjack documentation:"


def _format_tool_results(tool_results: list[dict[str, Any]]) -> str:
    if not tool_results:
        return "[]"
    return json.dumps(tool_results, indent=2, default=str)


def _format_citations(citations: list[dict[str, Any]]) -> str:
    if not citations:
        return "None"

    lines: list[str] = []
    for index, citation in enumerate(citations, start=1):
        title = str(citation.get("title", "Payjack documentation"))
        snippet = str(citation.get("snippet", "")).strip()
        source_path = str(citation.get("metadata", {}).get("source_path", "unknown"))
        lines.extend(
            [
                f"{index}. {title}",
                f"Source: {source_path}",
                f"Excerpt: {snippet}",
            ]
        )
    return "\n".join(lines)


def build_tool_summarizer_prompt(
    *,
    user_message: str,
    route: str,
    tool_results: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    grounding_mode: str,
) -> str:
    shared_sections = [
        f"Grounding mode: {grounding_mode}",
        f"User message: {user_message}",
        "Structured tool results:",
        _format_tool_results(tool_results),
    ]

    if grounding_mode == "hybrid":
        return "\n".join(
            [
                COMPANION_ANSWER_INSTRUCTION,
                "Use structured tool facts exactly as provided.",
                "Use accepted Payjack documentation only for Payjack-specific policy, fee, limit, product, or app claims.",
                "Do not invent missing Payjack policies, fees, limits, procedures, or transaction facts.",
                *shared_sections,
                ACCEPTED_DOCS_SECTION,
                _format_citations(citations),
                (
                    "Write a concise answer that clearly separates what came from the user's read-only data "
                    "from what came from Payjack documentation. If documentation does not fully answer the policy part, say what remains unverified."
                ),
            ]
        )

    if grounding_mode == "rag":
        return "\n".join(
            [
                COMPANION_ANSWER_INSTRUCTION,
                "Use structured tool facts exactly as provided.",
                "For documentation claims, use only the accepted Payjack citations below.",
                "Do not invent missing Payjack policies, fees, limits, or procedures.",
                *shared_sections,
                ACCEPTED_DOCS_SECTION,
                _format_citations(citations),
                (
                    "Write a concise answer grounded in the accepted citations. "
                    "If the citations do not fully answer the question, say what remains unverified."
                ),
            ]
        )

    if grounding_mode == "tool":
        return "\n".join(
            [
                COMPANION_ANSWER_INSTRUCTION,
                "Use the structured tool results exactly as provided.",
                "Do not claim documentation grounding when no accepted citations are present.",
                "Do not invent policy, fee, or limit details that are not in the tool output.",
                *shared_sections,
                ACCEPTED_DOCS_SECTION,
                "None",
                "Write a concise response that preserves the tool facts exactly.",
            ]
        )

    if route == "safe_general_route":
        return "\n".join(
            [
                COMPANION_ANSWER_INSTRUCTION,
                "This is a safe general question that does not require private user data or Payjack-specific documentation.",
                "Use general knowledge, keep the answer concise, and do not claim access to private account data.",
                "Do not give personalized regulated financial advice, guarantees, or instructions to bypass controls.",
                *shared_sections,
                ACCEPTED_DOCS_SECTION,
                "None",
                "Write a helpful general answer. If current or Payjack-specific facts would be required, say they are not verified here.",
            ]
        )

    return "\n".join(
        [
            COMPANION_ANSWER_INSTRUCTION,
            "No reliable Payjack documentation was retrieved for this request.",
            "Respond helpfully, but do not claim the answer is grounded in Payjack documentation.",
            (
                "If the user is asking for Payjack-specific facts about fees, limits, policies, or app procedures "
                "and you cannot verify them, say reliable Payjack documentation was not found."
            ),
            *shared_sections,
            ACCEPTED_DOCS_SECTION,
            "None",
            "Write a concise fallback answer from the base model only.",
        ]
    )
