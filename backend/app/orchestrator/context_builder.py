# app/orchestrator/context_builder.py
# 2026-04-16
"""Context builder module for constructing prompts to send to the LLM based on user messages, 
tool results, and retrieved context. This module is intentionally kept free of imports from other app modules to avoid circular import issues, 
since the context builder is used by multiple other modules. If you need to import something, 
consider whether it belongs in this file or if it should be passed in as an argument from the caller instead."""

from __future__ import annotations

from typing import Any

from app.llm.prompts.tool_summarizer_prompt import build_tool_summarizer_prompt

# This file is intentionally kept free of imports from other app modules to avoid circular import issues, since the context builder is used by multiple other modules. If you need to import something, consider whether it belongs in this file or if it should be passed in as an argument from the caller instead.

# This module is responsible for building the prompt that will be sent to the LLM for generation, based on the user message, tool results, and retrieved context. It encapsulates the logic for how to combine these different sources of information into a coherent prompt that the LLM can understand and use to generate a response. By centralizing this logic in one place, we can ensure consistency across different parts of the application and make it easier to maintain and update the prompt construction process as needed.
def build_generation_prompt(
    *,
    user_message: str, # e.g. "What is the revenue for Q1 2024?"
    tool_results: list[dict[str, Any]], # e.g. [{"tool_name": "get_payjack_data", "output": "result of tool call"}, ...]
    citations: list[dict[str, Any]], # e.g. [{"source": "file.txt", "text": "relevant excerpt from file.txt"}, ...]
    grounding_mode: str, # e.g. "retrieval", "tool_calls", "none"
) -> str:
    return build_tool_summarizer_prompt(
        user_message=user_message, # e.g. "What is the revenue for Q1 2024?"
        tool_results=tool_results, # e.g. [{"tool_name": "get_payjack_data", "output": "result of tool call"}, ...]
        citations=citations, # e.g. [{"source": "file.txt", "text": "relevant excerpt from file.txt"}, ...]
        grounding_mode=grounding_mode, # e.g. "retrieval", "tool_calls", "none"
    )
