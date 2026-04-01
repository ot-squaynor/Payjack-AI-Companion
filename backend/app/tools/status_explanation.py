# app/tools/status_explanation.py
# 2026-02-25
"""Purpose: Translate internal status codes to user-safe explanations (possibly backed by policy docs via RAG, but careful: deterministic mapping first, RAG only for generic docs)."""
##BRICK 1: Define the purpose and scope of the status explanation tool, emphasizing its deterministic nature and read-only access to pre-processed status data. Highlight that it does not perform I/O, LLM calls, RAG retrieval, or mutate the input dataframe.
"""
Deterministic status explanation tool for structured financial tool outputs.

This module converts already-computed deterministic tool results into
explanation-ready structured payloads. It does not perform financial
computation, dataframe access, I/O, LLM calls, or RAG retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

import logging

from backend.app.tools.recurring_detection import HIGH

logger = logging.getLogger(__name__)

EXPLANATION_TYPE_SPEND = "spend"
EXPLANATION_TYPE_TRANSACTIONS = "transactions"
EXPLANATION_TYPE_RECURRING = "recurring"
EXPLANATION_TYPE_BALANCE = "balance"

DETAIL_LEVEL_LOW = "low"
DETAIL_LEVEL_MEDIUM = "medium"
DETAIL_LEVEL_HIGH = "high"

TAG_HIGH_SPEND = "high_spend"
TAG_ANOMALY = "anomaly"
TAG_RECURRING = "recurring"
TAG_LARGE_TRANSACTION = "large_transaction"
TAG_MULTI_CURRENCY = "multi_currency"
TAG_EMPTY_RESULT = "empty_result"
TAG_TOP_CATEGORY = "top_category"
TAG_RECENT_ACTIVITY = "recent_activity"
TAG_HIGH_CONFIDENCE = "high_confidence"

DEFAULT_DETAIL_LEVEL: str = DETAIL_LEVEL_MEDIUM
DEFAULT_INCLUDE_WARNINGS: bool = True

ALLOWED_EXPLANATION_TYPES: frozenset[str] = frozenset(
    {
        EXPLANATION_TYPE_SPEND,
        EXPLANATION_TYPE_TRANSACTIONS,
        EXPLANATION_TYPE_RECURRING,
        EXPLANATION_TYPE_BALANCE,
    }
)

ALLOWED_DETAIL_LEVELS: frozenset[str] = frozenset(
    {
        DETAIL_LEVEL_LOW,
        DETAIL_LEVEL_MEDIUM,
        DETAIL_LEVEL_HIGH,
    }
)

ALLOWED_EXPLANATION_TAGS: frozenset[str] = frozenset(
    {
        TAG_HIGH_SPEND,
        TAG_ANOMALY,
        TAG_RECURRING,
        TAG_LARGE_TRANSACTION,
        TAG_MULTI_CURRENCY,
        TAG_EMPTY_RESULT,
        TAG_TOP_CATEGORY,
        TAG_RECENT_ACTIVITY,
        TAG_HIGH_CONFIDENCE,
    }
)


class StatusExplanationError(Exception):
    """Base exception for status explanation tool failures."""


class StatusExplanationInputError(StatusExplanationError):
    """Raised when explanation request inputs or source results are invalid."""


@dataclass(frozen=True, slots=True)
class StatusExplanationRequest:
    """Deterministic request contract for explanation-building flows."""

    explanation_type: Literal["spend", "transactions", "recurring", "balance"]
    focus: str | None = None
    include_warnings: bool = DEFAULT_INCLUDE_WARNINGS
    detail_level: Literal["low", "medium", "high"] = DEFAULT_DETAIL_LEVEL


@dataclass(frozen=True, slots=True)
class ExplanationBlock:
    """Typed explanation unit for downstream orchestration and formatting."""

    title: str
    value: str
    context: str | None = None
    tags: tuple[str, ...] = ()
    priority: int = 0


@dataclass(frozen=True, slots=True)
class StatusExplanationResult:
    """Structured explanation output for downstream orchestration."""

    blocks: tuple[ExplanationBlock, ...]
    summary_flags: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    source_type: str = ""
    confidence: str = "medium"

##BRICK 2: Implement input normalization and validation for the explanation request, ensuring that the explanation type, detail level, and include_warnings flag are properly validated and normalized. Also, implement a function to validate that the source result from the upstream tool matches the expected structure for the requested explanation type.
def _normalize_focus(value: Any) -> str | None:
    """Normalize an optional explanation focus value."""
    if value is None:
        return None

    if not isinstance(value, str):
        raise StatusExplanationInputError("focus must be a string or None.")

    cleaned = value.strip()
    return cleaned if cleaned else None


def normalize_status_explanation_request(
    *,
    explanation_type: str,
    focus: Any = None,
    include_warnings: bool = DEFAULT_INCLUDE_WARNINGS,
    detail_level: str = DEFAULT_DETAIL_LEVEL,
) -> StatusExplanationRequest:
    """Validate and normalize raw request values into a deterministic explanation request."""
    if not isinstance(explanation_type, str) or not explanation_type.strip():
        raise StatusExplanationInputError("explanation_type must be a non-empty string.")

    normalized_explanation_type = explanation_type.strip().lower()
    if normalized_explanation_type not in ALLOWED_EXPLANATION_TYPES:
        raise StatusExplanationInputError(
            f"Unsupported explanation_type '{explanation_type}'. "
            f"Allowed values: {sorted(ALLOWED_EXPLANATION_TYPES)}."
        )

    if not isinstance(detail_level, str) or not detail_level.strip():
        raise StatusExplanationInputError("detail_level must be a non-empty string.")

    normalized_detail_level = detail_level.strip().lower()
    if normalized_detail_level not in ALLOWED_DETAIL_LEVELS:
        raise StatusExplanationInputError(
            f"Unsupported detail_level '{detail_level}'. "
            f"Allowed values: {sorted(ALLOWED_DETAIL_LEVELS)}."
        )

    if not isinstance(include_warnings, bool):
        raise StatusExplanationInputError("include_warnings must be a boolean.")

    return StatusExplanationRequest(
        explanation_type=normalized_explanation_type,
        focus=_normalize_focus(focus),
        include_warnings=include_warnings,
        detail_level=normalized_detail_level,
    )


def validate_explanation_source_compatibility(
    source_result: Any,
    request: StatusExplanationRequest,
) -> None:
    """Validate that the upstream tool result matches the requested explanation type."""
    if request.explanation_type == EXPLANATION_TYPE_SPEND:
        required_attributes = ("total_amount", "transaction_count", "currency_breakdown")
    elif request.explanation_type == EXPLANATION_TYPE_TRANSACTIONS:
        required_attributes = ("records", "match_count", "applied_filters")
    elif request.explanation_type == EXPLANATION_TYPE_RECURRING:
        required_attributes = ("records", "match_count", "summary")
    elif request.explanation_type == EXPLANATION_TYPE_BALANCE:
        required_attributes = ("balances",)
    else:  # pragma: no cover
        raise StatusExplanationInputError(
            f"Unsupported explanation_type '{request.explanation_type}'."
        )

    missing_attributes = [
        attribute_name
        for attribute_name in required_attributes
        if not hasattr(source_result, attribute_name)
    ]
    if missing_attributes:
        raise StatusExplanationInputError(
            "Source result is incompatible with the requested explanation type. "
            f"Missing attributes: {missing_attributes}."
        )
    
##BRICK 3: Implement the core logic for building explanation blocks, deriving confidence levels, and merging warnings. Ensure that the explanation blocks are built with proper normalization and validation, confidence levels are derived based on source result characteristics, and warnings are merged without duplication while respecting the include_warnings flag.
def _normalize_string_value(value: Any, field_name: str) -> str:
    """Normalize a required explanation string field into a safe string."""
    if value is None:
        raise StatusExplanationInputError(f"{field_name} cannot be None.")

    normalized = str(value).strip()
    if not normalized:
        raise StatusExplanationInputError(f"{field_name} cannot be blank.")

    return normalized


def _normalize_optional_string_value(value: Any) -> str | None:
    """Normalize an optional explanation string field."""
    if value is None:
        return None

    normalized = str(value).strip()
    return normalized if normalized else None


def _normalize_tags(tags: Any) -> tuple[str, ...]:
    """Normalize explanation tags into a validated tuple."""
    if tags is None:
        return ()

    if isinstance(tags, str):
        candidate_tags = [tags]
    elif isinstance(tags, (list, tuple, set, frozenset)):
        candidate_tags = list(tags)
    else:
        raise StatusExplanationInputError("tags must be a string, sequence, or None.")

    normalized_tags: list[str] = []
    for tag in candidate_tags:
        if tag is None:
            continue

        if not isinstance(tag, str):
            raise StatusExplanationInputError("All explanation tags must be strings.")

        cleaned = tag.strip().lower()
        if not cleaned:
            continue

        if cleaned not in ALLOWED_EXPLANATION_TAGS:
            raise StatusExplanationInputError(
                f"Unsupported explanation tag '{cleaned}'. "
                f"Allowed values: {sorted(ALLOWED_EXPLANATION_TAGS)}."
            )

        normalized_tags.append(cleaned)

    return tuple(normalized_tags)


def _derive_priority(
    *,
    detail_level: str,
    is_primary: bool = False,
    has_warning: bool = False,
) -> int:
    """Derive a deterministic explanation-block priority."""
    base_priority_map = {
        DETAIL_LEVEL_LOW: 1,
        DETAIL_LEVEL_MEDIUM: 2,
        DETAIL_LEVEL_HIGH: 3,
    }

    if detail_level not in base_priority_map:
        raise StatusExplanationInputError(
            f"Unsupported detail_level '{detail_level}'. "
            f"Allowed values: {sorted(ALLOWED_DETAIL_LEVELS)}."
        )

    priority = base_priority_map[detail_level]

    if is_primary:
        priority += 2

    if has_warning:
        priority += 1

    return priority


def build_explanation_block(
    *,
    title: Any,
    value: Any,
    context: Any = None,
    tags: Any = None,
    priority: int,
) -> ExplanationBlock:
    """Build a validated explanation block."""
    if not isinstance(priority, int):
        raise StatusExplanationInputError("priority must be an integer.")

    return ExplanationBlock(
        title=_normalize_string_value(title, "title"),
        value=_normalize_string_value(value, "value"),
        context=_normalize_optional_string_value(context),
        tags=_normalize_tags(tags),
        priority=priority,
    )


def derive_explanation_confidence(source_result: Any) -> str:
    """Derive a deterministic explanation confidence label from the source result."""
    if hasattr(source_result, "summary"):
        summary = getattr(source_result, "summary", {})
        if isinstance(summary, dict):
            confidence_counts = summary.get("count_by_confidence")
            if isinstance(confidence_counts, dict):
                if confidence_counts.get("high", 0) > 0:
                    return "high"
                if confidence_counts.get("medium", 0) > 0:
                    return "medium"
                if confidence_counts.get("low", 0) > 0:
                    return "low"

    if hasattr(source_result, "warnings"):
        warnings = getattr(source_result, "warnings", ())
        if warnings:
            return "medium"

    return "high"


def merge_explanation_warnings(
    *,
    source_warnings: Any,
    include_warnings: bool,
    extra_warnings: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Merge source and explanation warnings deterministically."""
    if not include_warnings:
        return ()

    merged_warnings: list[str] = []

    if isinstance(source_warnings, (list, tuple)):
        for warning in source_warnings:
            if warning is None:
                continue
            normalized_warning = str(warning).strip()
            if normalized_warning:
                merged_warnings.append(normalized_warning)
    elif source_warnings is not None:
        normalized_warning = str(source_warnings).strip()
        if normalized_warning:
            merged_warnings.append(normalized_warning)

    for warning in extra_warnings:
        normalized_warning = str(warning).strip()
        if normalized_warning:
            merged_warnings.append(normalized_warning)

    deduplicated_warnings: list[str] = []
    seen: set[str] = set()
    for warning in merged_warnings:
        if warning not in seen:
            deduplicated_warnings.append(warning)
            seen.add(warning)

    return tuple(deduplicated_warnings)
##BRICK 4: Implement the specific logic for building explanation blocks for spend summaries, including the total spend block and grouped breakdown blocks. Ensure that the blocks are built with proper context, tags, and priority based on the characteristics of the source result and the request parameters.
def _build_spend_total_block(
    source_result: Any,
    request: StatusExplanationRequest,
) -> ExplanationBlock:
    """Build the primary total-spend explanation block."""
    currency_count = len(getattr(source_result, "currency_breakdown", {}))
    context = (
        f"Based on {source_result.transaction_count} transaction(s)"
        if currency_count <= 1
        else f"Based on {source_result.transaction_count} transaction(s) across {currency_count} currencies"
    )

    tags: list[str] = []
    if currency_count > 1:
        tags.append(TAG_MULTI_CURRENCY)

    return build_explanation_block(
        title="Total spend",
        value=str(source_result.total_amount),
        context=context,
        tags=tuple(tags),
        priority=_derive_priority(
            detail_level=request.detail_level,
            is_primary=True,
            has_warning=currency_count > 1,
        ),
    )


def _build_spend_grouped_blocks(
    source_result: Any,
    request: StatusExplanationRequest,
) -> tuple[ExplanationBlock, ...]:
    """Build grouped spend highlight blocks from grouped breakdown output."""
    grouped_breakdown = getattr(source_result, "grouped_breakdown", ())
    if not grouped_breakdown:
        return ()

    max_blocks_by_detail = {
        DETAIL_LEVEL_LOW: 1,
        DETAIL_LEVEL_MEDIUM: 3,
        DETAIL_LEVEL_HIGH: 5,
    }
    max_blocks = max_blocks_by_detail[request.detail_level]

    blocks: list[ExplanationBlock] = []
    for row in grouped_breakdown[:max_blocks]:
        normalized_key = str(row.key).strip() or "unknown"
        normalized_group_label = (
            request.focus.strip().replace("_", " ").title()
            if isinstance(request.focus, str) and request.focus.strip()
            else "Grouped spend"
        )

        tags: list[str] = []
        if getattr(source_result, "grouped_breakdown", ()):
            if len(blocks) == 0:
                tags.append(TAG_TOP_CATEGORY)

        context_parts = [f"{row.transaction_count} transaction(s)"]
        if row.currency is not None:
            context_parts.append(f"currency: {row.currency}")

        blocks.append(
            build_explanation_block(
                title=f"{normalized_group_label}: {normalized_key}",
                value=str(row.total_amount),
                context=" | ".join(context_parts),
                tags=tuple(tags),
                priority=_derive_priority(
                    detail_level=request.detail_level,
                    is_primary=False,
                    has_warning=(row.currency is None),
                ),
            )
        )

    return tuple(blocks)


def build_spend_summary_flags(source_result: Any) -> dict[str, Any]:
    """Build deterministic summary flags for spend explanations."""
    grouped_breakdown = getattr(source_result, "grouped_breakdown", ())
    currency_breakdown = getattr(source_result, "currency_breakdown", {})
    warnings = getattr(source_result, "warnings", ())

    top_group_key: str | None = None
    top_group_amount: str | None = None
    if grouped_breakdown:
        first_group = grouped_breakdown[0]
        top_group_key = str(first_group.key)
        top_group_amount = str(first_group.total_amount)

    return {
        "empty_result": int(getattr(source_result, "transaction_count", 0)) == 0,
        "has_grouped_breakdown": bool(grouped_breakdown),
        "multi_currency": len(currency_breakdown) > 1,
        "warning_count": len(warnings),
        "top_group_key": top_group_key,
        "top_group_amount": top_group_amount,
        "transaction_count": int(getattr(source_result, "transaction_count", 0)),
    }


def build_spend_explanation(
    source_result: Any,
    request: StatusExplanationRequest,
) -> tuple[tuple[ExplanationBlock, ...], dict[str, Any]]:
    """Build structured explanation blocks and flags for a spend-summary result."""
    blocks: list[ExplanationBlock] = []
    blocks.append(_build_spend_total_block(source_result, request))
    blocks.extend(_build_spend_grouped_blocks(source_result, request))

    summary_flags = build_spend_summary_flags(source_result)
    return tuple(blocks), summary_flags

##BRICK 5: Implement the specific logic for building explanation blocks for transaction lookups, including selecting the largest and most recent transactions, building sample transaction blocks, and deriving summary flags based on the characteristics of the returned records. Ensure that the blocks are built with proper context, tags, and priority based on the request parameters and source result characteristics.
def _select_largest_transaction_record(records: tuple[Any, ...]) -> Any | None:
    """Select the largest transaction record deterministically by amount."""
    if not records:
        return None

    return max(
        records,
        key=lambda record: (
            Decimal(str(record.amount)),
            str(record.timestamp),
            str(record.transaction_id),
        ),
    )


def _select_most_recent_transaction_record(records: tuple[Any, ...]) -> Any | None:
    """Select the most recent transaction record deterministically by timestamp."""
    if not records:
        return None

    return max(
        records,
        key=lambda record: (
            str(record.timestamp),
            Decimal(str(record.amount)),
            str(record.transaction_id),
        ),
    )


def _build_largest_transaction_block(
    source_result: Any,
    request: StatusExplanationRequest,
) -> ExplanationBlock | None:
    """Build the primary largest-transaction explanation block."""
    largest_record = _select_largest_transaction_record(getattr(source_result, "records", ()))
    if largest_record is None:
        return None

    return build_explanation_block(
        title="Largest returned transaction",
        value=str(largest_record.amount),
        context=(
            f"{largest_record.merchant} | {largest_record.category} | "
            f"{largest_record.timestamp} | {largest_record.currency}"
        ),
        tags=(TAG_LARGE_TRANSACTION,),
        priority=_derive_priority(
            detail_level=request.detail_level,
            is_primary=True,
            has_warning=False,
        ),
    )


def _build_most_recent_transaction_block(
    source_result: Any,
    request: StatusExplanationRequest,
) -> ExplanationBlock | None:
    """Build the most-recent-transaction explanation block."""
    recent_record = _select_most_recent_transaction_record(getattr(source_result, "records", ()))
    if recent_record is None:
        return None

    return build_explanation_block(
        title="Most recent returned transaction",
        value=str(recent_record.amount),
        context=(
            f"{recent_record.merchant} | {recent_record.category} | "
            f"{recent_record.timestamp} | {recent_record.currency}"
        ),
        tags=(TAG_RECENT_ACTIVITY,),
        priority=_derive_priority(
            detail_level=request.detail_level,
            is_primary=False,
            has_warning=False,
        ),
    )


def _build_transaction_sample_blocks(
    source_result: Any,
    request: StatusExplanationRequest,
) -> tuple[ExplanationBlock, ...]:
    """Build deterministic sample transaction blocks from returned records."""
    records = getattr(source_result, "records", ())
    if not records:
        return ()

    max_blocks_by_detail = {
        DETAIL_LEVEL_LOW: 1,
        DETAIL_LEVEL_MEDIUM: 2,
        DETAIL_LEVEL_HIGH: 4,
    }
    max_blocks = max_blocks_by_detail[request.detail_level]

    blocks: list[ExplanationBlock] = []
    for record in records[:max_blocks]:
        tags: list[str] = []
        if record == _select_most_recent_transaction_record(records):
            tags.append(TAG_RECENT_ACTIVITY)

        blocks.append(
            build_explanation_block(
                title=f"Transaction: {record.merchant}",
                value=str(record.amount),
                context=(
                    f"{record.category} | {record.timestamp} | "
                    f"{record.currency} | {record.direction}"
                ),
                tags=tuple(tags),
                priority=_derive_priority(
                    detail_level=request.detail_level,
                    is_primary=False,
                    has_warning=False,
                ),
            )
        )

    return tuple(blocks)


def build_transaction_summary_flags(source_result: Any) -> dict[str, Any]:
    """Build deterministic summary flags for transaction explanations."""
    records = getattr(source_result, "records", ())
    warnings = getattr(source_result, "warnings", ())
    largest_record = _select_largest_transaction_record(records)
    recent_record = _select_most_recent_transaction_record(records)

    currencies = sorted({str(record.currency) for record in records}) if records else []

    return {
        "empty_result": len(records) == 0,
        "multi_currency": len(currencies) > 1,
        "warning_count": len(warnings),
        "match_count": int(getattr(source_result, "match_count", 0)),
        "largest_transaction_id": (
            str(largest_record.transaction_id) if largest_record is not None else None
        ),
        "largest_transaction_amount": (
            str(largest_record.amount) if largest_record is not None else None
        ),
        "most_recent_transaction_id": (
            str(recent_record.transaction_id) if recent_record is not None else None
        ),
        "currencies": tuple(currencies),
    }


def build_transaction_explanation(
    source_result: Any,
    request: StatusExplanationRequest,
) -> tuple[tuple[ExplanationBlock, ...], dict[str, Any]]:
    """Build structured explanation blocks and flags for a transaction-lookup result."""
    blocks: list[ExplanationBlock] = []

    largest_block = _build_largest_transaction_block(source_result, request)
    if largest_block is not None:
        blocks.append(largest_block)

    recent_block = _build_most_recent_transaction_block(source_result, request)
    if recent_block is not None:
        blocks.append(recent_block)

    blocks.extend(_build_transaction_sample_blocks(source_result, request))

    summary_flags = build_transaction_summary_flags(source_result)
    return tuple(blocks), summary_flags

##BRICK 6: Implement the specific logic for building explanation blocks for recurring-payment detection, including selecting high-confidence recurring records, determining the primary recurring record, building explanation blocks for these records, and deriving summary flags based on the characteristics of the returned records and summary. Ensure that the blocks are built with proper context, tags, and priority based on the request parameters and source result characteristics.
def _select_high_confidence_recurring_records(
    records: tuple[Any, ...],
) -> tuple[Any, ...]:
    """Select recurring records marked with high confidence."""
    high_confidence_records = [
        record
        for record in records
        if str(record.confidence).strip().lower() == HIGH
    ]

    high_confidence_records.sort(
        key=lambda record: (
            Decimal(str(record.average_amount)),
            str(record.last_seen_timestamp),
            str(record.merchant).lower(),
            str(record.account_id).lower(),
        ),
        reverse=True,
    )

    return tuple(high_confidence_records)


def _select_primary_recurring_record(records: tuple[Any, ...]) -> Any | None:
    """Select the primary recurring record deterministically."""
    if not records:
        return None

    return max(
        records,
        key=lambda record: (
            Decimal(str(record.average_amount)),
            str(record.last_seen_timestamp),
            str(record.merchant).lower(),
            str(record.account_id).lower(),
        ),
    )


def _build_primary_recurring_block(
    source_result: Any,
    request: StatusExplanationRequest,
) -> ExplanationBlock | None:
    """Build the primary recurring-payment explanation block."""
    primary_record = _select_primary_recurring_record(
        getattr(source_result, "records", ())
    )
    if primary_record is None:
        return None

    tags: list[str] = [TAG_RECURRING]
    if str(primary_record.confidence).strip().lower() == HIGH:
        tags.append(TAG_HIGH_CONFIDENCE)

    return build_explanation_block(
        title="Primary recurring payment",
        value=str(primary_record.average_amount),
        context=(
            f"{primary_record.merchant} | {primary_record.cadence} | "
            f"{primary_record.last_seen_timestamp} | "
            f"{primary_record.currency or 'mixed currency'}"
        ),
        tags=tuple(tags),
        priority=_derive_priority(
            detail_level=request.detail_level,
            is_primary=True,
            has_warning=(primary_record.currency is None),
        ),
    )


def _build_high_confidence_recurring_blocks(
    source_result: Any,
    request: StatusExplanationRequest,
) -> tuple[ExplanationBlock, ...]:
    """Build recurring explanation blocks for high-confidence streams."""
    records = getattr(source_result, "records", ())
    high_confidence_records = _select_high_confidence_recurring_records(records)
    if not high_confidence_records:
        return ()

    max_blocks_by_detail = {
        DETAIL_LEVEL_LOW: 1,
        DETAIL_LEVEL_MEDIUM: 2,
        DETAIL_LEVEL_HIGH: 4,
    }
    max_blocks = max_blocks_by_detail[request.detail_level]

    blocks: list[ExplanationBlock] = []
    for record in high_confidence_records[:max_blocks]:
        blocks.append(
            build_explanation_block(
                title=f"High-confidence recurring: {record.merchant}",
                value=str(record.average_amount),
                context=(
                    f"{record.cadence} | {record.transaction_count} transaction(s) | "
                    f"{record.last_seen_timestamp} | {record.currency or 'mixed currency'}"
                ),
                tags=(TAG_RECURRING, TAG_HIGH_CONFIDENCE),
                priority=_derive_priority(
                    detail_level=request.detail_level,
                    is_primary=False,
                    has_warning=(record.currency is None),
                ),
            )
        )

    return tuple(blocks)


def _build_recurring_cadence_block(source_result: Any) -> ExplanationBlock | None:
    """Build a cadence distribution explanation block from recurring summary output."""
    summary = getattr(source_result, "summary", {})
    if not isinstance(summary, dict):
        return None

    cadence_counts = summary.get("count_by_cadence")
    if not isinstance(cadence_counts, dict) or not cadence_counts:
        return None

    ordered_parts = [
        f"{cadence}: {count}"
        for cadence, count in sorted(cadence_counts.items(), key=lambda item: item[0])
    ]

    return build_explanation_block(
        title="Recurring cadence distribution",
        value=" | ".join(ordered_parts),
        context="Count of recurring streams by cadence",
        tags=(TAG_RECURRING,),
        priority=1,
    )


def build_recurring_summary_flags(source_result: Any) -> dict[str, Any]:
    """Build deterministic summary flags for recurring explanations."""
    records = getattr(source_result, "records", ())
    warnings = getattr(source_result, "warnings", ())
    primary_record = _select_primary_recurring_record(records)
    high_confidence_count = len(_select_high_confidence_recurring_records(records))

    cadence_counts: dict[str, int] = {}
    for record in records:
        cadence = str(record.cadence).strip().lower()
        cadence_counts[cadence] = cadence_counts.get(cadence, 0) + 1

    return {
        "empty_result": len(records) == 0,
        "warning_count": len(warnings),
        "record_count": int(getattr(source_result, "match_count", 0)),
        "high_confidence_count": high_confidence_count,
        "irregular_only": bool(records) and all(bool(record.is_irregular) for record in records),
        "primary_merchant": (
            str(primary_record.merchant) if primary_record is not None else None
        ),
        "primary_average_amount": (
            str(primary_record.average_amount) if primary_record is not None else None
        ),
        "count_by_cadence": dict(sorted(cadence_counts.items(), key=lambda item: item[0])),
    }


def build_recurring_explanation(
    source_result: Any,
    request: StatusExplanationRequest,
) -> tuple[tuple[ExplanationBlock, ...], dict[str, Any]]:
    """Build structured explanation blocks and flags for a recurring-detection result."""
    blocks: list[ExplanationBlock] = []

    primary_block = _build_primary_recurring_block(source_result, request)
    if primary_block is not None:
        blocks.append(primary_block)

    blocks.extend(_build_high_confidence_recurring_blocks(source_result, request))

    cadence_block = _build_recurring_cadence_block(source_result)
    if cadence_block is not None and request.detail_level != DETAIL_LEVEL_LOW:
        blocks.append(cadence_block)

    summary_flags = build_recurring_summary_flags(source_result)
    return tuple(blocks), summary_flags

##BRICK 7: Implement a placeholder explanation builder for balance-tool support, which raises a clear and informative exception indicating that balance explanations are not yet available due to the lack of implementation of the underlying balance tool. Ensure that the exception message guides developers on the next steps for implementing this feature.
def build_balance_explanation(
    source_result: Any,
    request: StatusExplanationRequest,
) -> tuple[tuple[ExplanationBlock, ...], dict[str, Any]]:
    """Placeholder explanation builder for future balance-tool support."""
    raise StatusExplanationInputError(
        "Balance explanation is not yet available because app/tools/balances.py "
        "has not been implemented."
    )
##BRICK 8: Implement the main orchestration function for building explanations, which validates the source result compatibility, builds explanation blocks and summary flags based on the explanation type, and assembles the final structured explanation result with merged warnings and derived confidence levels. Ensure that the function handles each explanation type appropriately and returns a consistent output structure.
def assemble_summary_flags(
    *,
    base_flags: dict[str, Any] | None = None,
    source_type: str,
    confidence: str,
) -> dict[str, Any]:
    """Assemble final summary flags for the explanation result."""
    summary_flags = dict(base_flags or {})
    summary_flags["source_type"] = source_type
    summary_flags["explanation_confidence"] = confidence
    return summary_flags


def assemble_explanation_warnings(
    *,
    source_result: Any,
    request: StatusExplanationRequest,
    extra_warnings: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Assemble final explanation warnings from source and tool-level warnings."""
    source_warnings = getattr(source_result, "warnings", ())
    return merge_explanation_warnings(
        source_warnings=source_warnings,
        include_warnings=request.include_warnings,
        extra_warnings=extra_warnings,
    )


def build_explanation_metadata(
    *,
    source_type: str,
    source_result: Any,
    request: StatusExplanationRequest,
    base_flags: dict[str, Any] | None = None,
    extra_warnings: tuple[str, ...] = (),
) -> tuple[dict[str, Any], tuple[str, ...], str]:
    """Build final summary flags, warnings, and confidence metadata."""
    confidence = derive_explanation_confidence(source_result)
    summary_flags = assemble_summary_flags(
        base_flags=base_flags,
        source_type=source_type,
        confidence=confidence,
    )
    warnings = assemble_explanation_warnings(
        source_result=source_result,
        request=request,
        extra_warnings=extra_warnings,
    )
    return summary_flags, warnings, confidence
##BRICK 9: Implement the main function explain_status that orchestrates the entire explanation-building process, including validating inputs, building explanation blocks based on the explanation type, deriving summary flags and warnings, and returning a structured StatusExplanationResult. Ensure that the function handles all supported explanation types and logs relevant information about the explanation-building process.
def explain_status(
    source_result: Any,
    request: StatusExplanationRequest,
) -> StatusExplanationResult:
    """Build a deterministic structured explanation from an upstream tool result."""
    validate_explanation_source_compatibility(source_result, request)

    if request.explanation_type == EXPLANATION_TYPE_SPEND:
        blocks, base_flags = build_spend_explanation(source_result, request)
        source_type = EXPLANATION_TYPE_SPEND

    elif request.explanation_type == EXPLANATION_TYPE_TRANSACTIONS:
        blocks, base_flags = build_transaction_explanation(source_result, request)
        source_type = EXPLANATION_TYPE_TRANSACTIONS

    elif request.explanation_type == EXPLANATION_TYPE_RECURRING:
        blocks, base_flags = build_recurring_explanation(source_result, request)
        source_type = EXPLANATION_TYPE_RECURRING

    elif request.explanation_type == EXPLANATION_TYPE_BALANCE:
        blocks, base_flags = build_balance_explanation(source_result, request)
        source_type = EXPLANATION_TYPE_BALANCE

    else:  # pragma: no cover
        raise StatusExplanationInputError(
            f"Unsupported explanation_type '{request.explanation_type}'."
        )

    summary_flags, warnings, confidence = build_explanation_metadata(
        source_type=source_type,
        source_result=source_result,
        request=request,
        base_flags=base_flags,
    )

    logger.info(
        "Status explanation computed successfully.",
        extra={
            "source_type": source_type,
            "block_count": len(blocks),
            "warning_count": len(warnings),
            "confidence": confidence,
            "detail_level": request.detail_level,
            "include_warnings": request.include_warnings,
        },
    )

    return StatusExplanationResult(
        blocks=blocks,
        summary_flags=summary_flags,
        warnings=warnings,
        source_type=source_type,
        confidence=confidence,
    )
##BRICK 10: Implement a utility function to serialize the StatusExplanationResult into a JSON-friendly dictionary format, ensuring that all components of the result are properly converted into standard data types that can be easily serialized to JSON.
def status_explanation_result_to_dict(
    result: StatusExplanationResult,
) -> dict[str, Any]:
    """Serialize a status explanation result into a JSON-friendly dictionary."""
    return {
        "blocks": [
            {
                "title": block.title,
                "value": block.value,
                "context": block.context,
                "tags": list(block.tags),
                "priority": block.priority,
            }
            for block in result.blocks
        ],
        "summary_flags": dict(result.summary_flags),
        "warnings": list(result.warnings),
        "source_type": result.source_type,
        "confidence": result.confidence,
    }
##BRICK :

##BRICK :