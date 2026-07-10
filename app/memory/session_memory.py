from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any


MAX_SESSION_COUNT = 1024
MAX_TURN_COUNT = 8


@dataclass(frozen=True, slots=True)
class MemoryTurn:
    role: str
    content: str
    request_id: str | None = None
    route: str | None = None


@dataclass(frozen=True, slots=True)
class ToolMemoryFact:
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    artifact_version: str | None = None


@dataclass(frozen=True, slots=True)
class SessionMemorySnapshot:
    session_id: str
    turns: tuple[MemoryTurn, ...] = ()
    last_request_id: str | None = None
    last_route: str | None = None
    last_answer: str | None = None
    last_tool_facts: tuple[ToolMemoryFact, ...] = ()
    last_citations: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class MemoryFollowupResolution:
    answer: str
    route: str = "memory_context_route"
    source_request_id: str | None = None
    source_tool_name: str | None = None
    confidence: float = 0.0

    def to_debug_dict(self) -> dict[str, Any]:
        return {
            "resolved": True,
            "source_request_id": self.source_request_id,
            "source_tool_name": self.source_tool_name,
            "confidence": self.confidence,
        }


class InMemorySessionMemoryStore:
    """Bounded in-process session memory for short follow-up turns."""

    def __init__(
        self,
        *,
        max_sessions: int = MAX_SESSION_COUNT,
        max_turns: int = MAX_TURN_COUNT,
    ) -> None:
        self.max_sessions = max_sessions
        self.max_turns = max_turns
        self._sessions: OrderedDict[str, SessionMemorySnapshot] = OrderedDict()

    def get(self, session_id: str) -> SessionMemorySnapshot:
        snapshot = self._sessions.get(session_id)
        if snapshot is None:
            return SessionMemorySnapshot(session_id=session_id)
        self._sessions.move_to_end(session_id)
        return snapshot

    def record_exchange(
        self,
        *,
        session_id: str,
        user_message: str,
        assistant_answer: str,
        request_id: str,
        route: str,
        tool_facts: list[ToolMemoryFact] | None = None,
        citations: list[dict[str, Any]] | None = None,
    ) -> SessionMemorySnapshot:
        previous = self.get(session_id)
        turns = [
            *previous.turns,
            MemoryTurn(role="user", content=user_message),
            MemoryTurn(
                role="assistant",
                content=assistant_answer,
                request_id=request_id,
                route=route,
            ),
        ][-self.max_turns :]
        snapshot = SessionMemorySnapshot(
            session_id=session_id,
            turns=tuple(turns),
            last_request_id=request_id,
            last_route=route,
            last_answer=assistant_answer,
            last_tool_facts=tuple(deepcopy(tool_facts or [])),
            last_citations=tuple(deepcopy(citations or [])),
        )
        self._sessions[session_id] = snapshot
        self._sessions.move_to_end(session_id)
        while len(self._sessions) > self.max_sessions:
            self._sessions.popitem(last=False)
        return snapshot


_CEDI_FOLLOWUP_RE = re.compile(
    r"\b(?:cedis?|ghs|currency|amount|total|spent|spend)\b",
    re.IGNORECASE,
)
_CONFIRMATION_FOLLOWUP_RE = re.compile(
    r"^(?:are you sure|sure\??|confirm(?: that)?|is that right|double check|verify)$",
    re.IGNORECASE,
)


def _normalize_message(message: str) -> str:
    return " ".join(message.strip().lower().split())


def _latest_tool_fact(
    snapshot: SessionMemorySnapshot,
    tool_name: str,
) -> ToolMemoryFact | None:
    for fact in reversed(snapshot.last_tool_facts):
        if fact.name == tool_name:
            return fact
    return None


def _single_currency_amount(result: dict[str, Any]) -> tuple[str, str] | None:
    currency_breakdown = result.get("currency_breakdown")
    if isinstance(currency_breakdown, dict) and len(currency_breakdown) == 1:
        currency, amount = next(iter(currency_breakdown.items()))
        return str(currency), str(amount)

    total = result.get("total_amount")
    if total is None:
        return None
    return "GHS", str(total)


def _resolve_spend_followup(
    *,
    message: str,
    snapshot: SessionMemorySnapshot,
) -> MemoryFollowupResolution | None:
    spend_fact = _latest_tool_fact(snapshot, "spend_summary")
    if spend_fact is None:
        return None

    lowered = _normalize_message(message)
    is_currency_followup = _CEDI_FOLLOWUP_RE.search(lowered) is not None
    is_confirmation = _CONFIRMATION_FOLLOWUP_RE.fullmatch(lowered) is not None
    if not is_currency_followup and not is_confirmation:
        return None

    result = spend_fact.result
    amount_pair = _single_currency_amount(result)
    if amount_pair is None:
        return None
    currency, amount = amount_pair
    transaction_count = result.get("transaction_count")
    suffix = ""
    if transaction_count is not None:
        suffix = f" across {transaction_count} transactions"

    if is_confirmation:
        answer = (
            f"Yes. The previous answer came from the structured spend summary tool: "
            f"{amount} {currency}{suffix}."
        )
    else:
        answer = f"From the last spend summary, you spent {amount} {currency}{suffix}."

    return MemoryFollowupResolution(
        answer=answer,
        source_request_id=snapshot.last_request_id,
        source_tool_name=spend_fact.name,
        confidence=0.91 if is_currency_followup else 0.84,
    )


def resolve_contextual_followup(
    message: str,
    snapshot: SessionMemorySnapshot,
) -> MemoryFollowupResolution | None:
    if not snapshot.last_tool_facts:
        return None
    return _resolve_spend_followup(message=message, snapshot=snapshot)

