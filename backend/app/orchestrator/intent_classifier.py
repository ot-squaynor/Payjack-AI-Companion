from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
import re
from typing import Literal


RouteName = Literal[
    "deterministic_tool_route",
    "rag_route",
    "hybrid_route",
    "clarification_route",
    "refusal_route",
    "safe_general_route",
]


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
MONTH_NAMES_PATTERN = "|".join(MONTH_NAME_TO_NUMBER)

AMOUNT_ABOVE_RE = re.compile(
    r"\b(?:above|over|more than|greater than)\s+(?P<amount>\d+(?:\.\d+)?)\s*(?:cedis?|ghs)?\b"
)
STATUS_TERM_RE = re.compile(r"\b(?:status|pending|reversed|failed)\b")
LAST_N_RE = re.compile(r"\blast\s+(?P<count>\d+)\b")
PAST_N_RE = re.compile(
    r"\b(?:past|last)\s+(?P<count>\d+)\s+(?P<unit>days?|weeks?|months?)\b"
)
MONTH_RANGE_RE = re.compile(
    r"\b(?:from|between)\s+(?P<start>"
    + MONTH_NAMES_PATTERN
    + r")(?:\s+\d{1,2})?\s+(?:to|and)\s+(?P<end>"
    + MONTH_NAMES_PATTERN
    + r")(?:\s+\d{1,2})?\b"
)
MONTH_DAY_RANGE_RE = re.compile(
    r"\b(?:from|between)?\s*(?P<month>"
    + MONTH_NAMES_PATTERN
    + r")\s+(?P<start_day>\d{1,2})\s+(?:to|and)\s+(?:"
    + MONTH_NAMES_PATTERN
    + r"\s+)?(?P<end_day>\d{1,2})\b"
)
IN_MONTH_RE = re.compile(r"\b(?:in|during|for)\s+(?P<month>" + MONTH_NAMES_PATTERN + r")\b")
QUARTER_RE = re.compile(r"\bq(?P<quarter>[1-4])\b|\b(?P<word>first|second|third|fourth)\s+quarter\b")


CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "groceries": ("grocery", "groceries", "supermarket", "food"),
    "transport": ("transport", "fuel", "taxi", "ride", "bus"),
    "bills": ("bill", "bills", "utility", "utilities"),
    "shopping": ("shopping", "shop", "retail"),
    "fees": ("fee", "fees", "charge", "charges", "levy", "commission"),
    "cash": ("cash", "atm", "withdrawal"),
    "dining": ("dining", "restaurant", "restaurants"),
    "entertainment": ("entertainment", "streaming", "cinema"),
}

VAGUE_REQUESTS = {
    "what happened",
    "what happened?",
    "is this good",
    "is this good?",
    "can you check it",
    "can you check it?",
    "why is this high",
    "why is this high?",
    "check this",
    "check this?",
}

PAYJACK_DOC_TERMS = (
    "payjack",
    "jackinvest",
    "onboarding",
    "help centre",
    "help center",
    "faq",
    "faqs",
    "app usage",
    "feature",
    "features",
    "product",
    "products",
    "limit",
    "limits",
    "policy",
    "policies",
    "transfer limit",
    "kyc",
)
PAYJACK_DOC_WITHOUT_BRAND_TERMS = (
    "onboarding",
    "help centre",
    "help center",
    "transfer limits",
    "fees and limits",
    "app feature",
    "app usage",
)
USER_DATA_TERMS = (
    "transaction",
    "transactions",
    "spend",
    "spending",
    "spent",
    "balance",
    "balances",
    "subscription",
    "subscriptions",
    "recurring",
    "merchant",
    "merchants",
    "charged",
    "charge",
    "account activity",
    "payment",
    "payments",
)
PERSONAL_ANCHORS = (
    "my",
    "i ",
    "me",
    "mine",
    "this",
    "last",
    "show",
    "lookup",
    "look up",
    "summar",
    "compare",
    "do i",
    "have i",
)


@dataclass(frozen=True, slots=True)
class ToolPlan:
    name: str
    arguments: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IntentClassification:
    route: RouteName
    intent: str
    confidence: float
    requires_user_data: bool = False
    requires_policy_docs: bool = False
    is_read_only: bool = True
    clarification_question: str | None = None
    tool_plans: tuple[ToolPlan, ...] = ()


def _normalize(message: str) -> str:
    return " ".join(message.strip().lower().split())


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _month_range(current_date: date, month: int) -> tuple[str, str]:
    end_day = calendar.monthrange(current_date.year, month)[1]
    return date(current_date.year, month, 1).isoformat(), date(current_date.year, month, end_day).isoformat()


def _this_or_previous_month(current_date: date, *, previous: bool) -> tuple[str, str]:
    first_day_this_month = current_date.replace(day=1)
    if previous:
        previous_month_end = first_day_this_month - timedelta(days=1)
        return previous_month_end.replace(day=1).isoformat(), previous_month_end.isoformat()
    return first_day_this_month.isoformat(), current_date.isoformat()


def _relative_range(current_date: date, count: int, unit: str) -> tuple[str, str]:
    unit = unit.rstrip("s")
    if unit == "day":
        start = current_date - timedelta(days=count - 1)
    elif unit == "week":
        start = current_date - timedelta(weeks=count)
    else:
        month = current_date.month - count + 1
        year = current_date.year
        while month <= 0:
            month += 12
            year -= 1
        start = date(year, month, 1)
    return start.isoformat(), current_date.isoformat()


def _extract_date_filters(message: str, *, current_date: date) -> dict[str, object]:
    filters: dict[str, object] = {}
    if "today" in message:
        filters["start_date"] = current_date.isoformat()
        filters["end_date"] = current_date.isoformat()
        return filters
    if "yesterday" in message:
        yesterday = current_date - timedelta(days=1)
        filters["start_date"] = yesterday.isoformat()
        filters["end_date"] = yesterday.isoformat()
        return filters
    if "last month" in message:
        filters["start_date"], filters["end_date"] = _this_or_previous_month(current_date, previous=True)
        return filters
    if "this month" in message:
        filters["start_date"], filters["end_date"] = _this_or_previous_month(current_date, previous=False)
        return filters
    if "last year" in message:
        year = current_date.year - 1
        filters["start_date"] = date(year, 1, 1).isoformat()
        filters["end_date"] = date(year, 12, 31).isoformat()
        return filters
    if "this year" in message or "first six months of this year" in message:
        filters["start_date"] = date(current_date.year, 1, 1).isoformat()
        filters["end_date"] = date(current_date.year, 6 if "first six months" in message else current_date.month, 30 if "first six months" in message else current_date.day).isoformat()
        return filters

    past_match = PAST_N_RE.search(message)
    if past_match:
        filters["start_date"], filters["end_date"] = _relative_range(
            current_date,
            int(past_match.group("count")),
            past_match.group("unit"),
        )
        return filters

    quarter_match = QUARTER_RE.search(message)
    if quarter_match:
        quarter = quarter_match.group("quarter")
        if quarter is None:
            quarter = {"first": "1", "second": "2", "third": "3", "fourth": "4"}[quarter_match.group("word")]
        quarter_number = int(quarter)
        start_month = (quarter_number - 1) * 3 + 1
        end_month = start_month + 2
        filters["start_date"] = date(current_date.year, start_month, 1).isoformat()
        filters["end_date"] = date(
            current_date.year,
            end_month,
            calendar.monthrange(current_date.year, end_month)[1],
        ).isoformat()
        return filters

    month_day_match = MONTH_DAY_RANGE_RE.search(message)
    if month_day_match:
        month = MONTH_NAME_TO_NUMBER[month_day_match.group("month")]
        start_day = int(month_day_match.group("start_day"))
        end_day = int(month_day_match.group("end_day"))
        filters["start_date"] = date(current_date.year, month, start_day).isoformat()
        filters["end_date"] = date(current_date.year, month, end_day).isoformat()
        return filters

    month_range_match = MONTH_RANGE_RE.search(message)
    if month_range_match:
        start_month = MONTH_NAME_TO_NUMBER[month_range_match.group("start")]
        end_month = MONTH_NAME_TO_NUMBER[month_range_match.group("end")]
        end_year = current_date.year + (1 if end_month < start_month else 0)
        filters["start_date"] = date(current_date.year, start_month, 1).isoformat()
        filters["end_date"] = date(
            end_year,
            end_month,
            calendar.monthrange(end_year, end_month)[1],
        ).isoformat()
        return filters

    in_month_match = IN_MONTH_RE.search(message)
    if in_month_match:
        filters["start_date"], filters["end_date"] = _month_range(
            current_date,
            MONTH_NAME_TO_NUMBER[in_month_match.group("month")],
        )
        return filters

    return filters


def _extract_categories(message: str) -> tuple[str, ...]:
    categories: list[str] = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in message for keyword in keywords):
            categories.append(category)
    return tuple(dict.fromkeys(categories))


def _extract_minimum_amount_filter(message: str) -> dict[str, object]:
    match = AMOUNT_ABOVE_RE.search(message)
    if match is None:
        return {}
    return {"min_average_amount": match.group("amount")}


def _extract_limit(message: str, *, default: int) -> int:
    match = LAST_N_RE.search(message)
    if match is None:
        if "last transaction" in message or "latest transaction" in message:
            return 1
        return default
    return max(1, min(int(match.group("count")), 100))


def _extract_group_by(message: str) -> str | None:
    if "month-by-month" in message or "month by month" in message or "monthly" in message or "compare" in message:
        return "month"
    if "by merchant" in message or "merchant breakdown" in message:
        return "merchant"
    if "by category" in message or "category spend" in message or "across all categories" in message:
        return "category"
    return None


def _common_tool_arguments(message: str, *, current_date: date) -> dict[str, object]:
    arguments = _extract_date_filters(message, current_date=current_date)
    categories = _extract_categories(message)
    if categories:
        arguments["categories"] = categories
    return arguments


def _date_tool_arguments(message: str, *, current_date: date) -> dict[str, object]:
    return _extract_date_filters(message, current_date=current_date)


def _is_vague(message: str) -> bool:
    if message in VAGUE_REQUESTS:
        return True
    if len(message.split()) <= 3 and message in {"help", "check", "why", "what now"}:
        return True
    return False


def _is_payjack_documentation_query(message: str) -> bool:
    if "fee" in message and _is_user_data_query(message):
        return True
    if _contains_any(message, PAYJACK_DOC_WITHOUT_BRAND_TERMS):
        return True
    if "payjack" in message or "jackinvest" in message:
        return True
    if _contains_any(message, ("limit", "limits", "policy", "feature", "features", "product", "products", "app")):
        return _contains_any(message, PAYJACK_DOC_TERMS)
    return False


def _is_user_data_query(message: str) -> bool:
    if not _contains_any(message, USER_DATA_TERMS):
        return False
    if _contains_any(message, PERSONAL_ANCHORS):
        return True
    if message.startswith(("show ", "look up ", "lookup ", "summarize ", "summarise ", "compare ")):
        return True
    return False


def _select_tool_plans(message: str, *, current_date: date) -> tuple[ToolPlan, ...]:
    common_arguments = _common_tool_arguments(message, current_date=current_date)

    if "recurring" in message or "subscription" in message:
        return (
            ToolPlan(
                name="recurring_detection",
                arguments={**common_arguments, **_extract_minimum_amount_filter(message)},
            ),
        )

    if ("fee" in message or "fees" in message or "charged" in message) and _is_user_data_query(message):
        return (
            ToolPlan(
                name="fee_breakdown",
                arguments={
                    **_date_tool_arguments(message, current_date=current_date),
                    "limit": _extract_limit(message, default=10),
                },
            ),
        )

    if "balance" in message or "balances" in message:
        return (ToolPlan(name="balances", arguments={}),)

    if STATUS_TERM_RE.search(message):
        return (ToolPlan(name="status_explanation", arguments=_date_tool_arguments(message, current_date=current_date)),)

    if any(keyword in message for keyword in ("spend", "spending", "spent", "how much", "unusual", "compare")):
        arguments = dict(common_arguments)
        group_by = _extract_group_by(message)
        if group_by:
            arguments["group_by"] = group_by
        return (ToolPlan(name="spend_summary", arguments=arguments),)

    if any(keyword in message for keyword in ("transaction", "transactions", "merchant", "charged", "charge", "account activity", "payment")):
        return (
            ToolPlan(
                name="transaction_lookup",
                arguments={**common_arguments, "limit": _extract_limit(message, default=10)},
            ),
        )

    return ()


def _needs_spend_clarification(message: str, tool_plans: tuple[ToolPlan, ...]) -> bool:
    if not tool_plans or tool_plans[0].name != "spend_summary":
        return False
    arguments = tool_plans[0].arguments
    has_time_or_filter = any(
        key in arguments
        for key in ("start_date", "end_date", "categories", "merchants", "group_by")
    )
    generic_spend_request = re.fullmatch(r"(?:how much did i spend|summari[sz]e my spending|my spending)", message) is not None
    return generic_spend_request and not has_time_or_filter


def classify_intent(message: str, *, current_date: date | None = None) -> IntentClassification:
    current_date = current_date or date.today()
    lowered = _normalize(message)

    if not lowered or _is_vague(lowered):
        return IntentClassification(
            route="clarification_route",
            intent="ambiguous_request",
            confidence=0.74,
            clarification_question="What would you like me to check: a transaction, your spending, a balance, or a PayJack product question?",
        )

    requires_user_data = _is_user_data_query(lowered)
    requires_policy_docs = _is_payjack_documentation_query(lowered)
    tool_plans = _select_tool_plans(lowered, current_date=current_date) if requires_user_data else ()

    if _needs_spend_clarification(lowered, tool_plans):
        return IntentClassification(
            route="clarification_route",
            intent="missing_spend_scope",
            confidence=0.82,
            requires_user_data=True,
            clarification_question="Which date range or category should I use for the spending summary?",
        )

    if tool_plans and requires_policy_docs:
        return IntentClassification(
            route="hybrid_route",
            intent=f"{tool_plans[0].name}_with_policy_context",
            confidence=0.88,
            requires_user_data=True,
            requires_policy_docs=True,
            tool_plans=tool_plans,
        )

    if tool_plans:
        return IntentClassification(
            route="deterministic_tool_route",
            intent=tool_plans[0].name,
            confidence=0.87,
            requires_user_data=True,
            tool_plans=tool_plans,
        )

    if requires_policy_docs:
        return IntentClassification(
            route="rag_route",
            intent="payjack_documentation_question",
            confidence=0.84,
            requires_policy_docs=True,
        )

    return IntentClassification(
        route="safe_general_route",
        intent="safe_general_question",
        confidence=0.66,
    )
