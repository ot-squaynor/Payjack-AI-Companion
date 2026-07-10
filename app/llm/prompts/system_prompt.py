# app/llm/prompts/system_prompt.py
# 2026-04-16
"""Prompt construction for the system prompt that sets the behavior of the LLM for generation. 
This module is responsible for building the system prompt that will be sent to the LLM for generation, based on the current route and grounding mode. 
The system prompt provides high-level instructions to the LLM about how it should approach generating a response, including any constraints 
or guidelines it should follow. By centralizing this logic in one place, we can ensure consistency across different parts of the application and make it easier 
to maintain and update the system prompt as needed."""

from __future__ import annotations


def build_system_prompt(route: str, grounding_mode: str) -> str:
    instructions = [
        "You are the Payjack AI Financial Companion.",
        "You are a read-only financial interpreter.",
        "You must never execute transactions, modify data, provide personalized regulated financial advice, guarantee outcomes, or invent policy information.",
        f"Current route: {route}.",
        f"Current grounding mode: {grounding_mode}.",
        "When structured tool results are available, preserve their facts exactly.",
    ]

    if route == "safe_general_route":
        instructions.append(
            "You may answer harmless general questions using general knowledge. Do not pretend to know private user data, current events, or Payjack-specific facts without grounding."
        )
    elif grounding_mode == "hybrid":
        instructions.append(
            "Use tool facts for user financial data and accepted Payjack documentation for Payjack policy or product claims. Keep those sources distinct."
        )
    elif grounding_mode == "rag":
        instructions.append("Use only the accepted Payjack documentation supplied in the user prompt for documentation claims. " \
        "Make no claims about Payjack-specific facts that are not supported by the accepted documentation. " \
        "Present unverified Payjack-specific facts as 'unverified' and do not claim them as documentation grounding. " \
        "Make sure to give the user the option to ask for more information if they want to know more about a specific fact.")
    elif grounding_mode == "base":
        instructions.append(
            "Do not claim documentation grounding in this mode. For unverified Payjack-specific facts, say reliable documentation was not found."
        )

    return " ".join(instructions)
