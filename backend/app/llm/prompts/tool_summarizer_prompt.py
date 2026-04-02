from __future__ import annotations

import json
from typing import Any


def build_tool_summarizer_prompt(
    *,
    user_message: str,
    tool_results: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> str:
    return "\n".join(
        [
            f"User message: {user_message}",
            "Tool results:",
            json.dumps(tool_results, indent=2, default=str),
            "Citations:",
            json.dumps(citations, indent=2, default=str),
            (
                "Write a concise, grounded answer that preserves structured facts exactly. "
                "If citations are present, mention that the answer is grounded in Payjack documentation."
            ),
        ]
    )
