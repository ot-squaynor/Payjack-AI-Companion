from __future__ import annotations

from typing import Any

from app.llm.prompts.tool_summarizer_prompt import build_tool_summarizer_prompt


def build_generation_prompt(
    *,
    user_message: str,
    tool_results: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> str:
    return build_tool_summarizer_prompt(
        user_message=user_message,
        tool_results=tool_results,
        citations=citations,
    )
