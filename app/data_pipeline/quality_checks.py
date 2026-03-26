# app/data_pipeline/quality_checks.py
# 2026-02-25
"""Purpose: Gatekeeping (schema validation, missing fields, drift detection, doc quality, duplicate chunks).
This is a big win for fintech: it prevents bad KB content from poisoning retrieval."""

##BRICK 1:
"""
Deterministic quality checks for processed transaction data.

This module validates the final processed dataframe after normalization,
category mapping, and recurrence detection, producing structured and
auditable quality-check findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Sequence


logger = logging.getLogger(__name__)


class QualityCheckError(Exception):
    """Base exception for quality check failures."""


class QualityCheckInputError(QualityCheckError):
    """Raised when the dataframe cannot be validated due to missing structure."""


SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"


@dataclass(frozen=True, slots=True)
class QualityCheckFinding:
    """Represents a single quality check finding."""

    check_name: str
    severity: str
    message: str
    row_count: int
    sample_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class QualityCheckReport:
    """Represents the full quality check report."""

    passed: bool
    finding_count: int
    error_count: int
    warning_count: int
    info_count: int
    findings: tuple[QualityCheckFinding, ...]


@dataclass(frozen=True, slots=True)
class QualityCheckConfig:
    """Configuration for deterministic quality checks."""

    max_sample_ids_per_finding: int = 5
    allowed_directions: frozenset[str] = frozenset({"credit", "debit"})
    allowed_categories: frozenset[str] = frozenset()
    allowed_subcategories: frozenset[str] = frozenset()
    allowed_cadences: frozenset[str] = frozenset()
    allowed_confidence_levels: frozenset[str] = frozenset()
    min_timestamp: str = "2000-01-01"
    allow_future_timestamps: bool = False

##BRICK :

##BRICK :

##BRICK :

##BRICK :

##BRICK :