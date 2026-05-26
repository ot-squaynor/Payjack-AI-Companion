# app/llm/prompts/routing_prompt.py
# 2026-04-16
"""Prompt construction for routing user messages to the appropriate handling mode (tool, RAG, hybrid, clarify, refuse).
This module is responsible for building the prompt that will be sent to the LLM to determine how to route a user message based on its content.
By centralizing this logic in one place, we can ensure consistency in how routing decisions are made across different parts of the application 
and make it easier to maintain and update the routing logic as needed."""

from __future__ import annotations


def build_routing_prompt(message: str) -> str:
    return (
        "Classify the user request into one of: tool, rag, hybrid, clarify, refuse. "
        f"Message: {message}"
    )
