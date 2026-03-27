# app/tools/spend_summary.py
# 2026-02-25
"""Purpose: Deterministic aggregation (category totals, merchants, trends).
Critical rule: LLM must not change these outputs."""
##BRICK 1: Context and imports
"""
Deterministic spend summary tool for structured transaction data.

This module computes read-only spend aggregates from already-processed
transaction datasets. It does not perform I/O, LLM calls, RAG retrieval,
or any mutation of the input dataframe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

import logging

import pandas as pd

logger = logging.getLogger(__name__)

DEBIT = "debit"
CREDIT = "credit"

DEFAULT_DIRECTION: str = DEBIT
DEFAULT_GROUP_LIMIT: int = 10
DEFAULT_SORT_DESCENDING: bool = True

ALLOWED_DIRECTIONS: frozenset[str] = frozenset({DEBIT, CREDIT})

ALLOWED_GROUP_BY: frozenset[str] = frozenset(
    {
        "category",
        "subcategory",
        "merchant",
        "account",
        "currency",
        "month",
    }
)

REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        "transaction_id",
        "account_id",
        "timestamp",
        "amount",
        "currency",
        "direction",
        "category",
        "subcategory",
        "merchant",
    }
)


class SpendSummaryError(Exception):
    """Base exception for spend summary tool failures."""


class SpendSummaryInputError(SpendSummaryError):
    """Raised when spend summary inputs are invalid."""


@dataclass(frozen=True, slots=True)
class SpendSummaryRequest:
    """Deterministic request contract for spend summary queries."""

    user_id: str | None = None
    account_ids: tuple[str, ...] = ()
    start_date: str | None = None
    end_date: str | None = None
    categories: tuple[str, ...] = ()
    merchants: tuple[str, ...] = ()
    direction: Literal["debit", "credit"] = DEFAULT_DIRECTION
    group_by: Literal[
        "category",
        "subcategory",
        "merchant",
        "account",
        "currency",
        "month",
    ] | None = None
    limit: int = DEFAULT_GROUP_LIMIT


@dataclass(frozen=True, slots=True)
class GroupedSpendRow:
    """Single grouped spend summary row."""

    key: str
    total_amount: Decimal
    transaction_count: int
    currency: str | None = None


@dataclass(frozen=True, slots=True)
class SpendSummaryResult:
    """Structured spend summary output for downstream orchestration."""

    total_amount: Decimal
    transaction_count: int
    currency_breakdown: dict[str, Decimal]
    grouped_breakdown: tuple[GroupedSpendRow, ...] = ()
    applied_filters: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

##BRICK :

##BRICK :

##BRICK :

##BRICK :