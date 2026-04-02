# app/data_pipeline/quality_checks.py
# 2026-02-25
"""Purpose: Gatekeeping (schema validation, missing fields, drift detection, doc quality, duplicate chunks).
This is a big win for fintech: it prevents bad KB content from poisoning retrieval."""

from __future__ import annotations

##BRICK 1:
# Deterministic quality checks for processed transaction data.
# This module validates the final processed dataframe after normalization,
# category mapping, and recurrence detection, producing structured and
# auditable quality-check findings.

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

##BRICK 2: Check Implementations
import pandas as pd


CHECK_REQUIRED_COLUMNS = "check_required_columns"
CHECK_DUPLICATE_TRANSACTION_IDS = "check_duplicate_transaction_ids"
CHECK_NULL_CRITICAL_FIELDS = "check_null_critical_fields"
CHECK_INVALID_DIRECTIONS = "check_invalid_directions"
CHECK_INVALID_CATEGORIES = "check_invalid_categories"
CHECK_INVALID_SUBCATEGORIES = "check_invalid_subcategories"
CHECK_INVALID_RECURRENCE_CADENCE = "check_invalid_recurrence_cadence"
CHECK_INVALID_RECURRENCE_CONFIDENCE = "check_invalid_recurrence_confidence"
CHECK_IMPOSSIBLE_TIMESTAMPS = "check_impossible_timestamps"
CHECK_IMPOSSIBLE_AMOUNTS = "check_impossible_amounts"
CHECK_RECURRING_FIELD_CONSISTENCY = "check_recurring_field_consistency"


COL_TRANSACTION_ID = "transaction_id"
COL_TIMESTAMP = "timestamp"
COL_AMOUNT = "amount"
COL_DIRECTION = "direction"
COL_MERCHANT_MAPPED = "merchant_mapped"
COL_CATEGORY_MAPPED = "category_mapped"
COL_SUBCATEGORY_MAPPED = "subcategory_mapped"
COL_CATEGORY_MAPPING_SOURCE = "category_mapping_source"

COL_IS_RECURRING = "is_recurring"
COL_RECURRING_CADENCE = "recurrence_cadence"
COL_RECURRING_CONFIDENCE = "recurrence_confidence"
COL_RECURRING_GROUP_KEY = "recurrence_group_key"
COL_RECURRING_OCCURRENCE_COUNT = "recurrence_occurrence_count"


REQUIRED_PROCESSED_COLUMNS: frozenset[str] = frozenset(
    {
        COL_TRANSACTION_ID,
        COL_TIMESTAMP,
        COL_AMOUNT,
        COL_DIRECTION,
        COL_MERCHANT_MAPPED,
        COL_CATEGORY_MAPPED,
        COL_SUBCATEGORY_MAPPED,
        COL_CATEGORY_MAPPING_SOURCE,
        COL_IS_RECURRING,
        COL_RECURRING_CADENCE,
        COL_RECURRING_CONFIDENCE,
        COL_RECURRING_GROUP_KEY,
        COL_RECURRING_OCCURRENCE_COUNT,
    }
)
##BRICK 3: Default Configuration Values
DEFAULT_MAX_SAMPLE_IDS_PER_FINDING = 5
DEFAULT_MIN_TIMESTAMP = "2000-01-01"
DEFAULT_ALLOW_FUTURE_TIMESTAMPS = False

DEFAULT_ALLOWED_DIRECTIONS: frozenset[str] = frozenset({"credit", "debit"})

DEFAULT_ALLOWED_CATEGORIES: frozenset[str] = frozenset(
    {
        "income",
        "transfer",
        "groceries",
        "transport",
        "bills",
        "shopping",
        "entertainment",
        "healthcare",
        "education",
        "savings",
        "fees",
        "cash",
        "other",
    }
)

DEFAULT_ALLOWED_SUBCATEGORIES: frozenset[str] = frozenset(
    {
        "salary",
        "peer_transfer",
        "internal_transfer",
        "supermarket",
        "fuel",
        "ride_hailing",
        "utilities",
        "mobile_money",
        "subscriptions",
        "pharmacy",
        "tuition",
        "bank_fee",
        "atm_withdrawal",
        "general",
        "uncategorized",
    }
)

DEFAULT_ALLOWED_CADENCES: frozenset[str] = frozenset(
    {
        "none",
        "weekly",
        "biweekly",
        "monthly",
        "irregular",
    }
)

DEFAULT_ALLOWED_CONFIDENCE_LEVELS: frozenset[str] = frozenset(
    {
        "low",
        "medium",
        "high",
    }
)


def build_default_quality_check_config() -> QualityCheckConfig:
    """Build the default deterministic quality-check configuration."""
    return QualityCheckConfig(
        max_sample_ids_per_finding=DEFAULT_MAX_SAMPLE_IDS_PER_FINDING,
        allowed_directions=DEFAULT_ALLOWED_DIRECTIONS,
        allowed_categories=DEFAULT_ALLOWED_CATEGORIES,
        allowed_subcategories=DEFAULT_ALLOWED_SUBCATEGORIES,
        allowed_cadences=DEFAULT_ALLOWED_CADENCES,
        allowed_confidence_levels=DEFAULT_ALLOWED_CONFIDENCE_LEVELS,
        min_timestamp=DEFAULT_MIN_TIMESTAMP,
        allow_future_timestamps=DEFAULT_ALLOW_FUTURE_TIMESTAMPS,
    )
##BRICK 4: Input Validation and Finding Construction
def validate_quality_check_inputs(df: pd.DataFrame) -> None:
    """Validate that the dataframe contains all required processed columns."""
    missing_columns = REQUIRED_PROCESSED_COLUMNS.difference(df.columns)

    if missing_columns:
        missing_sorted = ", ".join(sorted(missing_columns))
        raise QualityCheckInputError(
            f"Input dataframe is missing required columns: {missing_sorted}."
        )

    if df.empty:
        logger.warning("Quality checks received an empty dataframe.")


def _truncate_sample_ids(
    ids: Sequence[object],
    max_items: int,
) -> tuple[str, ...]:
    """Return a truncated tuple of stringified sample IDs."""
    return tuple(str(i) for i in list(ids)[:max_items])


def make_finding(
    *,
    check_name: str,
    severity: str,
    message: str,
    row_ids: Sequence[object],
    config: QualityCheckConfig,
) -> QualityCheckFinding:
    """Construct a standardized QualityCheckFinding."""
    return QualityCheckFinding(
        check_name=check_name,
        severity=severity,
        message=message,
        row_count=len(row_ids),
        sample_ids=_truncate_sample_ids(
            row_ids,
            config.max_sample_ids_per_finding,
        ),
    )
##BRICK 5: Quality Check Implementations
def check_duplicate_transaction_ids(
    df: pd.DataFrame,
    config: QualityCheckConfig,
) -> list[QualityCheckFinding]:
    """Check for duplicate transaction identifiers."""
    duplicate_mask = df[COL_TRANSACTION_ID].duplicated(keep=False)

    if not duplicate_mask.any():
        return []

    duplicate_ids = df.loc[duplicate_mask, COL_TRANSACTION_ID].tolist()

    return [
        make_finding(
            check_name=CHECK_DUPLICATE_TRANSACTION_IDS,
            severity=SEVERITY_ERROR,
            message="Duplicate transaction_id values detected in processed dataset.",
            row_ids=duplicate_ids,
            config=config,
        )
    ]


def check_null_critical_fields(
    df: pd.DataFrame,
    config: QualityCheckConfig,
) -> list[QualityCheckFinding]:
    """Check for null values in critical processed columns."""
    critical_columns = (
        COL_TRANSACTION_ID,
        COL_TIMESTAMP,
        COL_AMOUNT,
        COL_DIRECTION,
        COL_MERCHANT_MAPPED,
        COL_CATEGORY_MAPPED,
        COL_SUBCATEGORY_MAPPED,
        COL_CATEGORY_MAPPING_SOURCE,
        COL_IS_RECURRING,
        COL_RECURRING_CADENCE,
        COL_RECURRING_CONFIDENCE,
    )

    findings: list[QualityCheckFinding] = []

    for column_name in critical_columns:
        null_mask = df[column_name].isna()
        if not null_mask.any():
            continue

        row_ids = df.loc[null_mask, COL_TRANSACTION_ID].tolist()

        findings.append(
            make_finding(
                check_name=CHECK_NULL_CRITICAL_FIELDS,
                severity=SEVERITY_ERROR,
                message=f"Null values detected in critical column '{column_name}'.",
                row_ids=row_ids,
                config=config,
            )
        )

    return findings
##BRICK 6: Enumerated Value Checks
def check_allowed_enums(
    df: pd.DataFrame,
    config: QualityCheckConfig,
) -> list[QualityCheckFinding]:
    """Validate that categorical fields stay within allowed enum sets."""
    findings: list[QualityCheckFinding] = []

    enum_checks = [
        (COL_DIRECTION, config.allowed_directions, CHECK_INVALID_DIRECTIONS),
        (COL_CATEGORY_MAPPED, config.allowed_categories, CHECK_INVALID_CATEGORIES),
        (COL_SUBCATEGORY_MAPPED, config.allowed_subcategories, CHECK_INVALID_SUBCATEGORIES),
        (COL_RECURRING_CADENCE, config.allowed_cadences, CHECK_INVALID_RECURRENCE_CADENCE),
        (COL_RECURRING_CONFIDENCE, config.allowed_confidence_levels, CHECK_INVALID_RECURRENCE_CONFIDENCE),
    ]

    for column_name, allowed_values, check_name in enum_checks:
        if not allowed_values:
            # Skip if config does not enforce this enum set
            continue

        invalid_mask = ~df[column_name].isin(allowed_values)

        if not invalid_mask.any():
            continue

        row_ids = df.loc[invalid_mask, COL_TRANSACTION_ID].tolist()

        findings.append(
            make_finding(
                check_name=check_name,
                severity=SEVERITY_ERROR,
                message=f"Invalid values detected in '{column_name}'.",
                row_ids=row_ids,
                config=config,
            )
        )

    return findings


def check_timestamp_sanity(
    df: pd.DataFrame,
    config: QualityCheckConfig,
) -> list[QualityCheckFinding]:
    """Validate timestamp integrity and policy compliance."""
    findings: list[QualityCheckFinding] = []

    # Ensure timestamps are datetime
    timestamps = pd.to_datetime(df[COL_TIMESTAMP], errors="coerce", utc=True)

    # Invalid timestamps
    invalid_mask = timestamps.isna()
    if invalid_mask.any():
        row_ids = df.loc[invalid_mask, COL_TRANSACTION_ID].tolist()
        findings.append(
            make_finding(
                check_name=CHECK_IMPOSSIBLE_TIMESTAMPS,
                severity=SEVERITY_ERROR,
                message="Invalid or non-coercible timestamps detected.",
                row_ids=row_ids,
                config=config,
            )
        )

    # Minimum timestamp policy
    min_ts = pd.to_datetime(config.min_timestamp, utc=True)
    too_early_mask = timestamps < min_ts
    if too_early_mask.any():
        row_ids = df.loc[too_early_mask, COL_TRANSACTION_ID].tolist()
        findings.append(
            make_finding(
                check_name=CHECK_IMPOSSIBLE_TIMESTAMPS,
                severity=SEVERITY_ERROR,
                message="Timestamps earlier than allowed minimum detected.",
                row_ids=row_ids,
                config=config,
            )
        )

    # Future timestamp policy
    if not config.allow_future_timestamps:
        now_ts = pd.Timestamp.utcnow()
        future_mask = timestamps > now_ts
        if future_mask.any():
            row_ids = df.loc[future_mask, COL_TRANSACTION_ID].tolist()
            findings.append(
                make_finding(
                    check_name=CHECK_IMPOSSIBLE_TIMESTAMPS,
                    severity=SEVERITY_WARNING,
                    message="Future timestamps detected.",
                    row_ids=row_ids,
                    config=config,
                )
            )

    return findings
##BRICK 7:
def check_amount_sanity(
    df: pd.DataFrame,
    config: QualityCheckConfig,
) -> list[QualityCheckFinding]:
    """Validate numeric amount integrity for processed transactions."""
    findings: list[QualityCheckFinding] = []

    amounts = pd.to_numeric(df[COL_AMOUNT], errors="coerce")

    invalid_mask = amounts.isna()
    if invalid_mask.any():
        row_ids = df.loc[invalid_mask, COL_TRANSACTION_ID].tolist()
        findings.append(
            make_finding(
                check_name=CHECK_IMPOSSIBLE_AMOUNTS,
                severity=SEVERITY_ERROR,
                message="Invalid or non-numeric amounts detected.",
                row_ids=row_ids,
                config=config,
            )
        )

    non_positive_mask = amounts <= 0
    if non_positive_mask.any():
        row_ids = df.loc[non_positive_mask, COL_TRANSACTION_ID].tolist()
        findings.append(
            make_finding(
                check_name=CHECK_IMPOSSIBLE_AMOUNTS,
                severity=SEVERITY_WARNING,
                message="Non-positive amounts detected in processed dataset.",
                row_ids=row_ids,
                config=config,
            )
        )

    return findings


def check_recurrence_consistency(
    df: pd.DataFrame,
    config: QualityCheckConfig,
) -> list[QualityCheckFinding]:
    """Validate logical consistency across recurrence-related output fields."""
    findings: list[QualityCheckFinding] = []

    recurring_true_mask = df[COL_IS_RECURRING].fillna(False).astype(bool)
    recurring_false_mask = ~recurring_true_mask

    missing_group_key_mask = recurring_true_mask & (
        df[COL_RECURRING_GROUP_KEY].isna()
        | (df[COL_RECURRING_GROUP_KEY].astype(str).str.strip() == "")
    )
    if missing_group_key_mask.any():
        row_ids = df.loc[missing_group_key_mask, COL_TRANSACTION_ID].tolist()
        findings.append(
            make_finding(
                check_name=CHECK_RECURRING_FIELD_CONSISTENCY,
                severity=SEVERITY_ERROR,
                message="Recurring rows are missing recurrence_group_key values.",
                row_ids=row_ids,
                config=config,
            )
        )

    low_occurrence_mask = recurring_true_mask & (
        pd.to_numeric(df[COL_RECURRING_OCCURRENCE_COUNT], errors="coerce")
        < config.max_sample_ids_per_finding
    )
    if low_occurrence_mask.any():
        row_ids = df.loc[low_occurrence_mask, COL_TRANSACTION_ID].tolist()
        findings.append(
            make_finding(
                check_name=CHECK_RECURRING_FIELD_CONSISTENCY,
                severity=SEVERITY_ERROR,
                message="Recurring rows have implausibly low recurrence_occurrence_count values.",
                row_ids=row_ids,
                config=config,
            )
        )

    inconsistent_false_mask = recurring_false_mask & (
        (df[COL_RECURRING_CADENCE] != "none")
        | (df[COL_RECURRING_CONFIDENCE] != "low")
    )
    if inconsistent_false_mask.any():
        row_ids = df.loc[inconsistent_false_mask, COL_TRANSACTION_ID].tolist()
        findings.append(
            make_finding(
                check_name=CHECK_RECURRING_FIELD_CONSISTENCY,
                severity=SEVERITY_WARNING,
                message="Non-recurring rows contain non-default cadence or confidence values.",
                row_ids=row_ids,
                config=config,
            )
        )

    return findings
##BRICK 8: Main Quality Check Runner
def run_quality_checks(
    df: pd.DataFrame,
    config: QualityCheckConfig | None = None,
) -> QualityCheckReport:
    """Run deterministic quality checks against the processed transaction dataframe."""
    resolved_config = config or build_default_quality_check_config()

    validate_quality_check_inputs(df)

    findings: list[QualityCheckFinding] = []
    findings.extend(check_duplicate_transaction_ids(df, resolved_config))
    findings.extend(check_null_critical_fields(df, resolved_config))
    findings.extend(check_allowed_enums(df, resolved_config))
    findings.extend(check_timestamp_sanity(df, resolved_config))
    findings.extend(check_amount_sanity(df, resolved_config))
    findings.extend(check_recurrence_consistency(df, resolved_config))

    error_count = sum(1 for finding in findings if finding.severity == SEVERITY_ERROR)
    warning_count = sum(1 for finding in findings if finding.severity == SEVERITY_WARNING)
    info_count = sum(1 for finding in findings if finding.severity == SEVERITY_INFO)

    report = QualityCheckReport(
        passed=error_count == 0,
        finding_count=len(findings),
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        findings=tuple(findings),
    )

    if report.passed:
        logger.info("Quality checks passed with %s findings.", report.finding_count)
    else:
        logger.warning(
            "Quality checks failed with %s errors, %s warnings, %s infos.",
            report.error_count,
            report.warning_count,
            report.info_count,
        )

    return report
##BRICK 9: Report Serialization

def quality_check_report_to_dict(report: QualityCheckReport) -> dict[str, object]:
    """Serialize a quality check report into a plain dictionary."""
    return {
        "passed": report.passed,
        "finding_count": report.finding_count,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
        "info_count": report.info_count,
        "findings": [
            {
                "check_name": finding.check_name,
                "severity": finding.severity,
                "message": finding.message,
                "row_count": finding.row_count,
                "sample_ids": list(finding.sample_ids),
            }
            for finding in report.findings
        ],
    }
##BRICK :
