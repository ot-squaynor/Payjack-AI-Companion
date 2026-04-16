from __future__ import annotations

import json
from typing import Any


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

    if grounding_mode == "rag":
        return "\n".join(
            [
                "Answer as the Payjack AI Financial Companion.",
                "Use structured tool facts exactly as provided.",
                "For documentation claims, use only the accepted Payjack citations below.",
                "Do not invent missing Payjack policies, fees, limits, or procedures.",
                *shared_sections,
                "Accepted Payjack documentation:",
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
                "Answer as the Payjack AI Financial Companion.",
                "Use the structured tool results exactly as provided.",
                "Do not claim documentation grounding when no accepted citations are present.",
                "Do not invent policy, fee, or limit details that are not in the tool output.",
                *shared_sections,
                "Accepted Payjack documentation:",
                "None",
                "Write a concise response that preserves the tool facts exactly.",
            ]
        )

    return "\n".join(
        [
            "Answer as the Payjack AI Financial Companion.",
            "No reliable Payjack documentation was retrieved for this request.",
            "Respond helpfully, but do not claim the answer is grounded in Payjack documentation.",
            (
                "If the user is asking for Payjack-specific facts about fees, limits, policies, or app procedures "
                "and you cannot verify them, say reliable Payjack documentation was not found."
            ),
            *shared_sections,
            "Accepted Payjack documentation:",
            "None",
            "Write a concise fallback answer from the base model only.",
        ]
    )
