# app/tools/transaction_lookup.py
# 2026-02-25
"""Purpose: Fetch transactions (by user, time window, filters).
Audit note: Must enforce access control here or in a shared data access layer."""

##BRICK 1: Define the purpose and scope of the transaction lookup tool, emphasizing its deterministic nature and read-only access to pre-processed transaction data. Highlight that it does not perform I/O, LLM calls, RAG retrieval, or mutate the input dataframe.
"""
Deterministic transaction lookup tool for structured transaction data.

This module retrieves read-only transaction records from already-processed
transaction datasets. It does not perform I/O, LLM calls, RAG retrieval,
or mutation of the input dataframe.
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

DEFAULT_LIMIT: int = 25
DEFAULT_SORT_BY: str = "timestamp"
DEFAULT_SORT_DESCENDING: bool = True

ALLOWED_DIRECTIONS: frozenset[str] = frozenset({DEBIT, CREDIT})
ALLOWED_SORT_FIELDS: frozenset[str] = frozenset(
    {
        "timestamp",
        "amount",
        "merchant",
        "category",
        "account_id",
        "transaction_id",
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
        "merchant",
        "category",
        "subcategory",
    }
)


class TransactionLookupError(Exception):
    """Base exception for transaction lookup tool failures."""


class TransactionLookupInputError(TransactionLookupError):
    """Raised when transaction lookup inputs are invalid."""


@dataclass(frozen=True, slots=True)
class TransactionLookupRequest:
    """Deterministic request contract for transaction lookup queries."""

    user_id: str | None = None
    transaction_ids: tuple[str, ...] = ()
    account_ids: tuple[str, ...] = ()
    merchants: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    direction: Literal["debit", "credit"] | None = None
    start_date: str | None = None
    end_date: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    limit: int = DEFAULT_LIMIT
    sort_by: Literal[
        "timestamp",
        "amount",
        "merchant",
        "category",
        "account_id",
        "transaction_id",
    ] = DEFAULT_SORT_BY
    sort_descending: bool = DEFAULT_SORT_DESCENDING


@dataclass(frozen=True, slots=True)
class TransactionRecord:
    """Typed transaction output row for downstream orchestration."""

    transaction_id: str
    account_id: str
    timestamp: str
    amount: Decimal
    currency: str
    direction: str
    merchant: str
    category: str
    subcategory: str


@dataclass(frozen=True, slots=True)
class TransactionLookupResult:
    """Structured transaction lookup output for downstream orchestration."""

    records: tuple[TransactionRecord, ...]
    match_count: int
    applied_filters: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
##BRICK :

##BRICK :

##BRICK :

##BRICK :

##BRICK :

##BRICK :

##BRICK :

##BRICK :

##BRICK :