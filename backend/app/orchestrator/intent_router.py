from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
import re


DATE_KEYWORD_PATTERNS = {
    "last_month": re.compile(r"\blast month\b"),
    "this_month": re.compile(r"\bthis month\b"),
}
LAST_N_RE = re.compile(r"\blast\s+(\d+)\b")


@dataclass(frozen=True, slots=True)
class RouteDecision:
    route: str
    reason: str
    tool_name: str | None = None
    tool_arguments: dict[str, object] = field(default_factory=dict)


def _month_date_range(current_date: date, *, previous: bool) -> tuple[str, str]:
    first_day_this_month = current_date.replace(day=1)
    if previous:
        last_day_previous_month = first_day_this_month - timedelta(days=1)
        start_date = last_day_previous_month.replace(day=1)
        end_date = last_day_previous_month
    else:
        start_date = first_day_this_month
        end_date = current_date
    return start_date.isoformat(), end_date.isoformat()


def _extract_common_filters(message: str) -> dict[str, object]:
    lowered = message.lower()
    filters: dict[str, object] = {}

    categories = []
    for category in ("groceries", "transport", "bills", "shopping", "fees", "cash"):
        if category in lowered:
            categories.append(category)
    if categories:
        filters["categories"] = tuple(categories)

    if DATE_KEYWORD_PATTERNS["last_month"].search(lowered):
        filters["start_date"], filters["end_date"] = _month_date_range(date.today(), previous=True)
    elif DATE_KEYWORD_PATTERNS["this_month"].search(lowered):
        filters["start_date"], filters["end_date"] = _month_date_range(date.today(), previous=False)

    return filters


def route_message(message: str) -> RouteDecision:
    lowered = message.strip().lower()
    common_filters = _extract_common_filters(lowered)

    if "recurring" in lowered or "subscription" in lowered:
        return RouteDecision(
            route="tool",
            reason="recurring_keywords",
            tool_name="recurring_detection",
            tool_arguments=common_filters,
        )

    if "last" in lowered and "transaction" in lowered:
        last_n_match = LAST_N_RE.search(lowered)
        limit = int(last_n_match.group(1)) if last_n_match else 5
        return RouteDecision(
            route="tool",
            reason="transaction_lookup_keywords",
            tool_name="transaction_lookup",
            tool_arguments={"limit": limit, **common_filters},
        )

    if any(keyword in lowered for keyword in ("spend", "spent", "how much")):
        return RouteDecision(
            route="tool",
            reason="spend_summary_keywords",
            tool_name="spend_summary",
            tool_arguments=common_filters,
        )

    if any(keyword in lowered for keyword in ("balance", "balances")):
        return RouteDecision(
            route="tool",
            reason="balance_keywords",
            tool_name="balances",
            tool_arguments={},
        )

    if any(keyword in lowered for keyword in ("status", "pending", "reversed", "failed")):
        return RouteDecision(
            route="tool",
            reason="status_keywords",
            tool_name="status_explanation",
            tool_arguments=common_filters,
        )

    if any(keyword in lowered for keyword in ("how do i", "feature", "fee", "limit", "policy", "help", "what is")):
        return RouteDecision(
            route="rag",
            reason="documentation_keywords",
        )

    return RouteDecision(
        route="clarify",
        reason="no_confident_route",
    )
