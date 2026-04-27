from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
import re


DATE_KEYWORD_PATTERNS = {
    "last_month": re.compile(r"\blast month\b"),
    "this_month": re.compile(r"\bthis month\b"),
}
AMOUNT_ABOVE_RE = re.compile(
    r"\b(?:above|over|more than|greater than)\s+(?P<amount>\d+(?:\.\d+)?)\s*(?:cedis?|ghs)?\b"
)
LAST_N_RE = re.compile(r"\blast\s+(\d+)\b")
MONTH_NAME_TO_NUMBER = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
MONTH_RANGE_PATTERNS = (
    re.compile(
        r"\bfrom\s+(?P<start>" + "|".join(MONTH_NAME_TO_NUMBER) + r")\s+to\s+(?P<end>" + "|".join(MONTH_NAME_TO_NUMBER) + r")\b"
    ),
    re.compile(
        r"\bbetween\s+(?P<start>" + "|".join(MONTH_NAME_TO_NUMBER) + r")\s+and\s+(?P<end>" + "|".join(MONTH_NAME_TO_NUMBER) + r")\b"
    ),
)


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

    filters.update(_extract_month_range_filters(lowered, current_date=date.today()))

    return filters


def _extract_minimum_amount_filter(message: str) -> dict[str, object]:
    match = AMOUNT_ABOVE_RE.search(message)
    if match is None:
        return {}
    return {"min_average_amount": match.group("amount")}


def _extract_month_range_filters(message: str, *, current_date: date) -> dict[str, object]:
    for pattern in MONTH_RANGE_PATTERNS:
        match = pattern.search(message)
        if match is None:
            continue

        start_month = MONTH_NAME_TO_NUMBER[match.group("start")]
        end_month = MONTH_NAME_TO_NUMBER[match.group("end")]
        start_year = current_date.year
        end_year = current_date.year
        if end_month < start_month:
            end_year += 1

        end_day = calendar.monthrange(end_year, end_month)[1]
        return {
            "start_date": date(start_year, start_month, 1).isoformat(),
            "end_date": date(end_year, end_month, end_day).isoformat(),
        }

    return {}


def route_message(message: str) -> RouteDecision:
    lowered = message.strip().lower()
    common_filters = _extract_common_filters(lowered)

    if "recurring" in lowered or "subscription" in lowered:
        recurring_filters = {**common_filters, **_extract_minimum_amount_filter(lowered)}
        return RouteDecision(
            route="tool",
            reason="recurring_keywords",
            tool_name="recurring_detection",
            tool_arguments=recurring_filters,
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

    if "transaction" in lowered and ("start_date" in common_filters or "end_date" in common_filters):
        return RouteDecision(
            route="tool",
            reason="transaction_date_range_keywords",
            tool_name="transaction_lookup",
            tool_arguments=common_filters,
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
