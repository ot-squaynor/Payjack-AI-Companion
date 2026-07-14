# app/orchestrator/intent_classifier.py
# 2026-04-16
"""Intent classification module for classifying user messages into handling routes and extracting relevant information for tool calls.
This module is responsible for analyzing user messages and determining the appropriate handling route (tool, RAG, hybrid, clarify, refuse) 
based on the content of the message. It also extracts relevant information from the message, such as date filters, categories, and other parameters
that can be used for tool calls. By centralizing this logic in one place, we can ensure consistency in how user messages are interpreted across 
different parts of the application and make it easier to maintain and update the classification logic as needed."""

# IMPORTS
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
import re
from typing import Literal

# Define the possible route names as a literal type for better type checking and clarity in the codebase.
RouteName = Literal[
    "deterministic_tool_route",
    "rag_route",
    "hybrid_route",
    "clarification_route",
    "refusal_route",
    "safe_general_route",
]

# Mapping of month names to their corresponding numbers for easier date filter extraction from user messages.
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

# Pattern for matching month names
MONTH_NAMES_PATTERN = "|".join(MONTH_NAME_TO_NUMBER)
# Regular expressions for extracting information from user messages, such as amounts, statuses, date ranges, and vague requests.
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

# Keywords for categorizing transactions into different categories based on the presence of certain terms in the user message.
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

# Common vague requests that lack sufficient information for classification and may require clarification from the user to determine their intent and the appropriate handling route. This set can be expanded as we identify more vague requests in user interactions.
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

# Terms that indicate a user is asking about Payjack documentation or policies, which may require RAG or hybrid handling routes.
PAYJACK_DOC_TERMS = (
    "payjack",
    "jackinvest",
    "onboarding",
    "verification",
    "verify",
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
    "transfer limits",
    "failed transfer",
    "failed transfers",
    "reversal",
    "reversals",
    "dispute",
    "disputes",
    "chargeback",
    "chargebacks",
    "account security",
    "security",
    "privacy",
    "eligibility",
    "requirements",
    "terms",
    "conditions",
    "support",
    "risk",
    "risks",
    "kyc",
)

# Terms that indicate a user is asking about their personal financial data, which may require tool-based handling routes.
PAYJACK_DOC_WITHOUT_BRAND_TERMS = (
    "onboarding",
    "kyc",
    "verification",
    "verify identity",
    "help centre",
    "help center",
    "transfer limits",
    "failed transfer",
    "failed transfers",
    "reversal",
    "reversals",
    "dispute",
    "disputes",
    "chargeback",
    "chargebacks",
    "account security",
    "privacy policy",
    "eligibility requirements",
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

# Data class for defining the structure of a tool plan, which includes the name of the tool to be called and the arguments to be passed to that tool based on the user's message and intent.
@dataclass(frozen=True, slots=True)
class ToolPlan:
    name: str
    arguments: dict[str, object] = field(default_factory=dict)

# Data class for defining the structure of an intent classification result, which includes the determined route for handling the user message, the identified intent, confidence level, and any relevant flags or information about the requirements for handling the message (such as whether user data or policy documents are needed, whether the response should be read-only, any clarification questions to ask the user, and any tool plans that should be executed). This structured format allows for consistent handling of user messages across different parts of the application based on their classified intent.
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

# Helper function for normalizing user messages by stripping leading/trailing whitespace, converting to lowercase, and collapsing multiple spaces into a single space. This helps ensure that the intent classification logic can operate on a consistent format of the user message, improving the accuracy of pattern matching and keyword detection.
def _normalize(message: str) -> str:
    """Normalize the user message by stripping whitespace, converting to lowercase, and collapsing multiple spaces."""
    return " ".join(message.strip().lower().split())

# Helper function for checking if any of a given set of terms are present in a text, which is used for determining whether a user message contains certain keywords that indicate specific intents or requirements for handling the message.
def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    """Check if any of the specified terms are present in the given text."""
    return any(term in text for term in terms)

# Helper function for calculating the start and end dates for a given month in the current year, which is used for extracting date filters from user messages that specify a particular month for querying financial data. This function takes into account the varying number of days in each month to ensure accurate date ranges are generated for tool calls that require date-based filtering.
def _month_range(current_date: date, month: int) -> tuple[str, str]:
    """Calculate the start and end dates for a given month in the current year."""
    end_day = calendar.monthrange(current_date.year, month)[1]
    return date(current_date.year, month, 1).isoformat(), date(current_date.year, month, end_day).isoformat()

# Helper function for calculating the start and end dates for either the current month or the previous month based on the user's message, which is used for extracting date filters from user messages that specify "this month" or "last month". This function determines the appropriate date range to use for tool calls that require monthly filtering of financial data.
def _this_or_previous_month(current_date: date, *, previous: bool) -> tuple[str, str]:
    """Calculate the start and end dates for either the current month or the previous month based on the user's message."""
    first_day_this_month = current_date.replace(day=1)
    if previous:
        previous_month_end = first_day_this_month - timedelta(days=1)
        return previous_month_end.replace(day=1).isoformat(), previous_month_end.isoformat()
    return first_day_this_month.isoformat(), current_date.isoformat()

# Helper function for calculating the start and end dates for a relative date range based on the user's message, such as "past 7 days" or "last 3 months". This function takes into account the current date and the specified count and unit of time to generate an appropriate date range for tool calls that require relative date filtering of financial data.
def _relative_range(current_date: date, count: int, unit: str) -> tuple[str, str]:
    """Calculate the start and end dates for a relative date range based on the user's message."""
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

# Helper function for extracting date filters from a user message by checking for various patterns that indicate specific date ranges, such as "today", "yesterday", "last month", "this month", "last year", "this year", relative date ranges like "past 7 days", specific quarters, and specific month-day ranges. This function returns a dictionary of date filter arguments that can be used for tool calls that require date-based filtering of financial data based on the user's message.
def _date_filter_range(start_date: str, end_date: str) -> dict[str, object]:
    return {"start_date": start_date, "end_date": end_date}


def _explicit_date_filters(message: str, *, current_date: date) -> dict[str, object] | None:
    if "today" in message:
        return _date_filter_range(current_date.isoformat(), current_date.isoformat())
    if "yesterday" in message:
        yesterday = current_date - timedelta(days=1)
        return _date_filter_range(yesterday.isoformat(), yesterday.isoformat())
    if "last month" in message:
        return _date_filter_range(
            *_this_or_previous_month(current_date, previous=True)
        )
    if "this month" in message:
        return _date_filter_range(
            *_this_or_previous_month(current_date, previous=False)
        )
    if "last year" in message:
        year = current_date.year - 1
        return _date_filter_range(
            date(year, 1, 1).isoformat(),
            date(year, 12, 31).isoformat(),
        )
    if "this year" in message or "first six months of this year" in message:
        end_month = 6 if "first six months" in message else current_date.month
        end_day = 30 if "first six months" in message else current_date.day
        return _date_filter_range(
            date(current_date.year, 1, 1).isoformat(),
            date(current_date.year, end_month, end_day).isoformat(),
        )
    return None


def _relative_date_filters(message: str, *, current_date: date) -> dict[str, object] | None:
    past_match = PAST_N_RE.search(message)
    if past_match is None:
        return None

    return _date_filter_range(
        *_relative_range(
            current_date,
            int(past_match.group("count")),
            past_match.group("unit"),
        )
    )


def _quarter_date_filters(message: str, *, current_date: date) -> dict[str, object] | None:
    quarter_match = QUARTER_RE.search(message)
    if quarter_match is None:
        return None

    quarter = quarter_match.group("quarter")
    if quarter is None:
        quarter = {"first": "1", "second": "2", "third": "3", "fourth": "4"}[
            quarter_match.group("word")
        ]
    quarter_number = int(quarter)
    start_month = (quarter_number - 1) * 3 + 1
    end_month = start_month + 2
    return _date_filter_range(
        date(current_date.year, start_month, 1).isoformat(),
        date(
            current_date.year,
            end_month,
            calendar.monthrange(current_date.year, end_month)[1],
        ).isoformat(),
    )


def _calendar_date_filters(message: str, *, current_date: date) -> dict[str, object] | None:
    month_day_match = MONTH_DAY_RANGE_RE.search(message)
    if month_day_match:
        month = MONTH_NAME_TO_NUMBER[month_day_match.group("month")]
        return _date_filter_range(
            date(current_date.year, month, int(month_day_match.group("start_day"))).isoformat(),
            date(current_date.year, month, int(month_day_match.group("end_day"))).isoformat(),
        )

    month_range_match = MONTH_RANGE_RE.search(message)
    if month_range_match:
        start_month = MONTH_NAME_TO_NUMBER[month_range_match.group("start")]
        end_month = MONTH_NAME_TO_NUMBER[month_range_match.group("end")]
        end_year = current_date.year + (1 if end_month < start_month else 0)
        return _date_filter_range(
            date(current_date.year, start_month, 1).isoformat(),
            date(
                end_year,
                end_month,
                calendar.monthrange(end_year, end_month)[1],
            ).isoformat(),
        )

    in_month_match = IN_MONTH_RE.search(message)
    if in_month_match:
        return _date_filter_range(
            *_month_range(
                current_date,
                MONTH_NAME_TO_NUMBER[in_month_match.group("month")],
            )
        )
    return None


def _extract_date_filters(message: str, *, current_date: date) -> dict[str, object]:
    """Extract date filters from the user message based on various patterns indicating specific date ranges."""
    for resolver in (
        _explicit_date_filters,
        _relative_date_filters,
        _quarter_date_filters,
        _calendar_date_filters,
    ):
        filters = resolver(message, current_date=current_date)
        if filters is not None:
            return filters
    return {}

# Helper function for extracting categories from a user message by checking for the presence of keywords associated with different categories of transactions (such as groceries, transport, bills, etc.) and returning a tuple of identified categories that can be used for tool calls that require category-based filtering of financial data based on the user's message.
def _extract_categories(message: str) -> tuple[str, ...]:
    """Extract categories from the user message based on the presence of keywords associated with different transaction categories."""
    categories: list[str] = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in message for keyword in keywords):
            categories.append(category)
    return tuple(dict.fromkeys(categories))

# Helper function for extracting a minimum amount filter from a user message by checking for patterns that indicate the user is asking about transactions above a certain amount, and returning a dictionary with the appropriate filter argument that can be used for tool calls that require amount-based filtering of financial data based on the user's message.
def _extract_minimum_amount_filter(message: str) -> dict[str, object]:
    """Extract a minimum amount filter from the user message based on patterns indicating transactions above a certain amount."""
    match = AMOUNT_ABOVE_RE.search(message)
    if match is None:
        return {}
    return {"min_average_amount": match.group("amount")}

# Helper function for extracting a limit on the number of transactions to return from a user message by checking for patterns that indicate the user is asking about the "last N" transactions, and returning the appropriate limit value that can be used for tool calls that require limiting the number of results based on the user's message. If no specific limit is mentioned, a default value is used, and if the message contains vague references to recent transactions, a default limit of 1 is applied.
def _extract_limit(message: str, *, default: int) -> int:
    """Extract a limit on the number of transactions to return from the user message based on patterns indicating "last N" transactions or vague references to recent transactions."""
    match = LAST_N_RE.search(message)
    if match is None:
        if "last transaction" in message or "latest transaction" in message:
            return 1
        return default
    return max(1, min(int(match.group("count")), 100))

# Helper function for extracting a grouping parameter from a user message by checking for patterns that indicate the user is asking for a breakdown of spending or transactions by month, merchant, or category, and returning the appropriate grouping value that can be used for tool calls that require grouping results based on the user's message.
def _extract_group_by(message: str) -> str | None:
    """Extract a grouping parameter from the user message based on patterns indicating a breakdown by month, merchant, or category."""
    if "month-by-month" in message or "month by month" in message or "monthly" in message or "compare" in message:
        return "month"
    if "by merchant" in message or "merchant breakdown" in message:
        return "merchant"
    if "by category" in message or "category spend" in message or "across all categories" in message:
        return "category"
    return None

# Helper function for checking if a user message is considered vague based on a predefined set of vague requests and certain patterns that indicate a lack of specificity in the user's query. This function helps identify messages that may require clarification from the user to determine their intent and the appropriate handling route.
def _common_tool_arguments(message: str, *, current_date: date) -> dict[str, object]:
    """Extract common tool arguments from the user message, such as date filters and categories, 
    that can be used for various tool calls based on the content of the message."""
    arguments = _extract_date_filters(message, current_date=current_date)
    categories = _extract_categories(message)
    if categories:
        arguments["categories"] = categories
    return arguments

# Helper function for extracting date filters from a user message by checking for various patterns that indicate specific date ranges, such as "today", "yesterday", "last month", "this month", "last year", "this year", relative date ranges like "past 7 days", specific quarters, and specific month-day ranges. This function returns a dictionary of date filter arguments that can be used for tool calls that require date-based filtering of financial data based on the user's message.
def _date_tool_arguments(message: str, *, current_date: date) -> dict[str, object]:
    """Extract date filters from the user message based on various patterns indicating specific date ranges, 
    and return them as arguments for tool calls that require date-based filtering."""
    return _extract_date_filters(message, current_date=current_date)

# Helper function for checking if a user message is considered vague based on a predefined set of vague requests and certain patterns that indicate a lack of specificity in the user's query. This function helps identify messages that may require clarification from the user to determine their intent and the appropriate handling route.
def _is_vague(message: str) -> bool:
    """Check if the user message is considered vague based on predefined vague requests and certain patterns indicating a lack of specificity."""
    if message in VAGUE_REQUESTS:
        return True
    if len(message.split()) <= 3 and message in {"help", "check", "why", "what now"}:
        return True
    return False

# Helper function for determining if a user message is asking about Payjack documentation or policies by checking for the presence of certain keywords and patterns that indicate the user is seeking information about Payjack-specific features, fees, limits, policies, or procedures. This function helps identify messages that may require RAG or hybrid handling routes based on their content.
def _is_payjack_documentation_query(message: str) -> bool:
    """Check if the user message is asking about Payjack documentation or policies based on the presence of certain keywords and patterns 
    indicating a query about Payjack-specific information."""
    if "fee" in message and _is_user_data_query(message):
        return True
    if _contains_any(message, PAYJACK_DOC_WITHOUT_BRAND_TERMS):
        return True
    if "payjack" in message or "jackinvest" in message:
        return True
    if _contains_any(message, ("limit", "limits", "policy", "feature", "features", "product", "products", "app")):
        return _contains_any(message, PAYJACK_DOC_TERMS)
    return False

# Helper function for determining if a user message is asking about their personal financial data by checking for the presence of certain keywords and patterns that indicate the user is seeking information about their transactions, spending, balances, or other personal financial data. This function helps identify messages that may require tool-based handling routes based on their content.
def _is_user_data_query(message: str) -> bool:
    """Check if the user message is asking about their personal financial data based on the presence of certain keywords and patterns
    indicating a query about transactions, spending, balances, or other personal financial information."""
    if not _contains_any(message, USER_DATA_TERMS):
        return False
    if _contains_any(message, PERSONAL_ANCHORS):
        return True
    if message.startswith(("show ", "look up ", "lookup ", "summarize ", "summarise ", "compare ")):
        return True
    return False

# Helper function for selecting the appropriate tool plans based on the content of the user message and the current date. This function checks for various patterns and keywords in the message to determine which tools should be called and with what arguments to retrieve the necessary information for generating a response to the user's query.
def _select_tool_plans(message: str, *, current_date: date) -> tuple[ToolPlan, ...]:
    """Select the appropriate tool plans based on the content of the user message and the current date by checking for various patterns
    and keywords that indicate specific queries about transactions, spending, balances, fees, and other personal financial data."""
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

# Helper function for determining if a user message that contains a request for a spending summary requires clarification about the scope of the spending being queried (such as date range or category) based on the presence of certain patterns in the message and the arguments extracted for the spend_summary tool plan. This function helps identify cases where the user's request is too vague to determine the appropriate scope for the spending summary and may require a clarification question to be asked to ensure accurate handling of the query.
def _needs_spend_clarification(message: str, tool_plans: tuple[ToolPlan, ...]) -> bool:
    """Determine if a user message that contains a request for a spending summary requires clarification about the scope 
    of the spending being queried based on the presence of certain patterns in the message and the arguments
      extracted for the spend_summary tool plan."""
    if not tool_plans or tool_plans[0].name != "spend_summary":
        return False
    arguments = tool_plans[0].arguments
    has_time_or_filter = any(
        key in arguments
        for key in ("start_date", "end_date", "categories", "merchants", "group_by")
    )
    generic_spend_request = re.fullmatch(r"(?:how much did i spend|summari[sz]e my spending|my spending)", message) is not None
    return generic_spend_request and not has_time_or_filter

# Function for classifying the intent of a user message by analyzing its content and determining the appropriate handling route, identified intent, confidence level, and any relevant requirements or tool plans based on the presence of certain keywords, patterns, and extracted information from the message. This function serves as the core of the intent classification logic, allowing the application to route user messages to the correct handling mode (tool, RAG, hybrid, clarification, refusal) based on their classified intent and the specific information they contain.
def classify_intent(message: str, *, current_date: date | None = None) -> IntentClassification:
    """Classify the intent of a user message by analyzing its content and determining the appropriate handling route, 
    identified intent, confidence level, and any relevant requirements or tool plans based on the presence of certain keywords, 
    patterns, and extracted information from the message."""
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
