# app/data_pipeline/category_mapping.py
# 2026-02-26
"""Purpose: Map raw document categories (e.g., 'policy', 'help') to standardized tags for consistent retrieval and filtering."""

##BRICK 1: Header, imports, logger, exceptions, and config dataclasses
"""
Deterministic category mapping for normalized transaction data.

This module converts normalized transaction category signals into a canonical
business taxonomy that downstream recurrence logic, quality checks, and
financial tools can rely on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Mapping, Sequence

import pandas as pd


logger = logging.getLogger(__name__)


class CategoryMappingError(Exception):
    """Base exception for category mapping failures."""


class CategoryMappingInputError(CategoryMappingError):
    """Raised when the input dataframe contract is invalid."""


class CategoryMappingConfigError(CategoryMappingError):
    """Raised when mapping configuration is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class CategoryMappingRule:
    """Deterministic rule for assigning a canonical category outcome."""

    priority: int
    source_field: str
    match_type: str
    match_value: str
    target_category: str
    target_subcategory: str
    direction_constraint: str | None = None
    merchant_constraint: str | None = None


@dataclass(frozen=True, slots=True)
class CategoryMappingConfig:
    """Configuration bundle for canonical category mapping behavior."""

    allowed_categories: frozenset[str]
    allowed_subcategories: frozenset[str]
    merchant_alias_map: Mapping[str, str] = field(default_factory=dict)
    category_alias_map: Mapping[str, str] = field(default_factory=dict)
    rules: Sequence[CategoryMappingRule] = field(default_factory=tuple)
    default_category: str = "other"
    default_subcategory: str = "uncategorized"
##BRICK 2:

##BRICK 3:

##BRICK 4:

##BRICK 5:

##BRICK 6:

##BRICK 7: 

##BRICK 8: 

##BRICK 9: 
