from __future__ import annotations


def build_routing_prompt(message: str) -> str:
    return (
        "Classify the user request into one of: tool, rag, hybrid, clarify, refuse. "
        f"Message: {message}"
    )
