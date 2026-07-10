import pandas as pd
import pytest

from app.data_pipeline import category_mapping as category
from app.data_pipeline import normalization
from app.data_pipeline import quality_checks as quality
from app.data_pipeline import recurring_logic as recurring


def test_normalize_transactions_cleans_values_and_drops_invalid_rows() -> None:
    raw = pd.DataFrame(
        [
            {
                "transaction_id": " txn-001 ",
                "account_id": " acc-001 ",
                "timestamp": "2026-03-28T10:00:00+00:00",
                "amount": "-45.50",
                "currency": "cedi",
                "merchant": "  melcom gh!!! ",
                "category": "supermarket",
                "description": "  weekly   shop  ",
            },
            {
                "transaction_id": " txn-bad ",
                "account_id": " acc-001 ",
                "timestamp": "not-a-date",
                "amount": "oops",
                "currency": "cedi",
                "merchant": "bad row",
                "category": "misc",
                "description": "drop me",
            },
        ]
    )

    config = normalization.NormalizationConfig(
        default_currency="GHS",
        drop_invalid_rows=True,
    )

    normalized = normalization.normalize_transactions(raw, config)

    assert len(normalized) == 1
    row = normalized.iloc[0]
    assert row["transaction_id"] == "txn-001"
    assert row["account_id"] == "acc-001"
    assert row["amount"] == -45.5
    assert row["currency"] == "GHS"
    assert row["merchant_clean"] == "Melcom Gh"
    assert row["category"] == "groceries"
    assert row["description"] == "weekly shop"
    assert row["direction"] == "debit"
    assert row["date"] == "2026-03-28"
    assert row["month"] == "2026-03"


def test_normalize_bundle_cleans_supported_dataset_types() -> None:
    bundle = {
        "accounts": pd.DataFrame(
            [
                {
                    "account_id": " acc-001 ",
                    "account_name": "  Main   Wallet ",
                    "account_type": "checking",
                    "currency": "ghc",
                }
            ]
        ),
        "fees_and_limits": pd.DataFrame(
            [
                {
                    "item_id": " fee-1 ",
                    "item_type": "charges",
                    "value": "12.5",
                    "unit": " ghs ",
                    "notes": "  atm   charge ",
                }
            ]
        ),
        "products": pd.DataFrame(
            [
                {
                    "product_id": " prod-1 ",
                    "product_name": "  Payjack   Card ",
                    "product_type": "CARD",
                }
            ]
        ),
        "metadata": pd.DataFrame(
            [
                {
                    "key": "  Source ",
                    "value": "  monthly   export ",
                    "source": "  backoffice ",
                }
            ]
        ),
    }

    normalized = normalization.normalize_bundle(
        bundle,
        normalization.NormalizationConfig(default_currency="GHS"),
    )

    assert normalized["accounts"].iloc[0].to_dict() == {
        "account_id": "acc-001",
        "account_name": "Main Wallet",
        "account_type": "current",
        "currency": "GHS",
    }
    assert normalized["fees_and_limits"].iloc[0].to_dict() == {
        "item_id": "fee-1",
        "item_type": "fee",
        "value": 12.5,
        "unit": "GHS",
        "notes": "atm charge",
    }
    assert normalized["products"].iloc[0].to_dict() == {
        "product_id": "prod-1",
        "product_name": "Payjack Card",
        "product_type": "card",
    }
    assert normalized["metadata"].iloc[0].to_dict() == {
        "key": "source",
        "value": "monthly export",
        "source": "backoffice",
    }


def _mapping_input(rows: list[dict[str, object]]) -> pd.DataFrame:
    defaults = {
        category.COL_TRANSACTION_ID: "txn-default",
        category.COL_AMOUNT: 10.0,
        category.COL_DIRECTION: "debit",
        category.COL_TIMESTAMP: "2026-01-01T00:00:00Z",
        category.COL_MERCHANT_NORMALIZED: "unknown",
        category.COL_CATEGORY_NORMALIZED: "other",
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


def test_map_categories_applies_alias_rules_fallbacks_and_summary() -> None:
    df = _mapping_input(
        [
            {
                category.COL_TRANSACTION_ID: "txn-rule",
                category.COL_MERCHANT_NORMALIZED: "melcom gh",
                category.COL_CATEGORY_NORMALIZED: "supermarket",
            },
            {
                category.COL_TRANSACTION_ID: "txn-alias",
                category.COL_CATEGORY_NORMALIZED: "shopping",
            },
            {
                category.COL_TRANSACTION_ID: "txn-default",
                category.COL_CATEGORY_NORMALIZED: "mystery",
            },
        ]
    )

    mapped = category.map_categories(df)

    assert mapped[category.COL_CATEGORY_MAPPED].tolist() == [
        "groceries",
        "shopping",
        "other",
    ]
    assert mapped[category.COL_SUBCATEGORY_MAPPED].tolist() == [
        "supermarket",
        "general",
        "uncategorized",
    ]
    assert mapped[category.COL_CATEGORY_MAPPING_SOURCE].tolist() == [
        "rule:30",
        "category_alias",
        "default_fallback",
    ]
    assert category.mapping_coverage_summary(mapped) == {
        "total_rows": 3,
        "default_fallback_rows": 1,
        "category_alias_rows": 1,
        "rule_mapped_rows": 1,
        "source::rule:30": 1,
        "source::category_alias": 1,
        "source::default_fallback": 1,
    }


def test_map_categories_supports_regex_rules_and_validates_inputs() -> None:
    regex_rule = category.CategoryMappingRule(
        priority=1,
        source_field=category.COL_MERCHANT_NORMALIZED,
        match_type=category.MATCH_REGEX,
        match_value=r"^netflix",
        target_category="entertainment",
        target_subcategory="subscriptions",
    )
    config = category.CategoryMappingConfig(
        allowed_categories=category.DEFAULT_ALLOWED_CATEGORIES,
        allowed_subcategories=category.DEFAULT_ALLOWED_SUBCATEGORIES,
        rules=(regex_rule,),
        default_category=category.DEFAULT_CATEGORY,
        default_subcategory=category.DEFAULT_SUBCATEGORY,
    )
    df = _mapping_input(
        [
            {
                category.COL_TRANSACTION_ID: "txn-streaming",
                category.COL_MERCHANT_NORMALIZED: "netflix gh",
                category.COL_CATEGORY_NORMALIZED: "subscription",
            }
        ]
    )

    mapped = category.map_categories(df, config)

    assert mapped.loc[0, category.COL_CATEGORY_MAPPED] == "entertainment"
    assert mapped.loc[0, category.COL_SUBCATEGORY_MAPPED] == "subscriptions"
    assert mapped.loc[0, category.COL_CATEGORY_MAPPING_SOURCE] == "rule:1"

    with pytest.raises(category.CategoryMappingInputError):
        category.validate_category_mapping_inputs(pd.DataFrame())

    with pytest.raises(category.CategoryMappingConfigError):
        invalid_config = category.CategoryMappingConfig(
            allowed_categories=frozenset({"other"}),
            allowed_subcategories=category.DEFAULT_ALLOWED_SUBCATEGORIES,
            rules=(regex_rule,),
            default_category="other",
            default_subcategory=category.DEFAULT_SUBCATEGORY,
        )
        category.validate_category_mapping_config(invalid_config)


def _recurring_input(rows: list[dict[str, object]]) -> pd.DataFrame:
    defaults = {
        recurring.COL_ACCOUNT_ID: "acc-001",
        recurring.COL_DIRECTION: "debit",
        recurring.COL_MERCHANT_MAPPED: "streaming service",
        recurring.COL_CATEGORY_MAPPED: "entertainment",
        recurring.COL_SUBCATEGORY_MAPPED: "subscriptions",
        recurring.COL_AMOUNT: 50.0,
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


def test_detect_recurring_transactions_marks_monthly_group_and_summary() -> None:
    df = _recurring_input(
        [
            {
                recurring.COL_TRANSACTION_ID: "txn-jan",
                recurring.COL_TIMESTAMP: "2026-01-01T09:00:00Z",
            },
            {
                recurring.COL_TRANSACTION_ID: "txn-jan-end",
                recurring.COL_TIMESTAMP: "2026-01-31T09:00:00Z",
            },
            {
                recurring.COL_TRANSACTION_ID: "txn-mar-start",
                recurring.COL_TIMESTAMP: "2026-03-03T09:00:00Z",
            },
            {
                recurring.COL_TRANSACTION_ID: "txn-apr-start",
                recurring.COL_TIMESTAMP: "2026-04-02T09:00:00Z",
            },
            {
                recurring.COL_TRANSACTION_ID: "txn-once",
                recurring.COL_TIMESTAMP: "2026-04-10T09:00:00Z",
                recurring.COL_MERCHANT_MAPPED: "one off merchant",
                recurring.COL_AMOUNT: 7.0,
            },
        ]
    )

    detected = recurring.detect_recurring_transactions(df)
    recurring_rows = detected[detected[recurring.COL_TRANSACTION_ID] != "txn-once"]
    one_off = detected.loc[
        detected[recurring.COL_TRANSACTION_ID] == "txn-once"
    ].iloc[0]

    assert recurring_rows[recurring.COL_IS_RECURRING].tolist() == [True] * 4
    assert set(recurring_rows[recurring.COL_RECURRING_CADENCE]) == {
        recurring.CADENCE_MONTHLY
    }
    assert set(recurring_rows[recurring.COL_RECURRING_CONFIDENCE]) == {
        recurring.CONFIDENCE_HIGH
    }
    assert set(recurring_rows[recurring.COL_RECURRING_OCCURRENCE_COUNT]) == {4}
    assert recurring_rows[recurring.COL_RECURRING_GROUP_KEY].str.len().min() > 0
    assert bool(one_off[recurring.COL_IS_RECURRING]) is False
    assert one_off[recurring.COL_RECURRING_CADENCE] == recurring.CADENCE_NONE

    summary = recurring.recurrence_summary(detected)
    assert summary["total_rows"] == 5
    assert summary["recurring_rows"] == 4
    assert summary["non_recurring_rows"] == 1
    assert summary["cadence::monthly"] == 4
    assert summary["cadence::none"] == 1
    assert summary["confidence::high"] == 4
    assert summary["confidence::low"] == 1


def test_detect_recurring_transactions_validates_config_and_coerced_values() -> None:
    with pytest.raises(recurring.RecurringLogicConfigError):
        recurring.validate_recurring_detection_config(
            recurring.RecurringDetectionConfig(min_group_size=1)
        )

    bad_df = _recurring_input(
        [
            {
                recurring.COL_TRANSACTION_ID: "txn-bad",
                recurring.COL_TIMESTAMP: "not-a-date",
                recurring.COL_AMOUNT: "not-a-number",
            }
        ]
    )

    with pytest.raises(recurring.RecurringLogicInputError):
        recurring.detect_recurring_transactions(bad_df)


def _quality_row(**overrides: object) -> dict[str, object]:
    row = {
        quality.COL_TRANSACTION_ID: "txn-001",
        quality.COL_TIMESTAMP: "2026-01-01T00:00:00Z",
        quality.COL_AMOUNT: 25.0,
        quality.COL_DIRECTION: "debit",
        quality.COL_MERCHANT_MAPPED: "melcom",
        quality.COL_CATEGORY_MAPPED: "groceries",
        quality.COL_SUBCATEGORY_MAPPED: "supermarket",
        quality.COL_CATEGORY_MAPPING_SOURCE: "rule:30",
        quality.COL_IS_RECURRING: False,
        quality.COL_RECURRING_CADENCE: "none",
        quality.COL_RECURRING_CONFIDENCE: "low",
        quality.COL_RECURRING_GROUP_KEY: "",
        quality.COL_RECURRING_OCCURRENCE_COUNT: 1,
    }
    row.update(overrides)
    return row


def test_quality_checks_pass_for_valid_processed_rows() -> None:
    report = quality.run_quality_checks(
        pd.DataFrame(
            [
                _quality_row(),
                _quality_row(
                    **{
                        quality.COL_TRANSACTION_ID: "txn-002",
                        quality.COL_IS_RECURRING: True,
                        quality.COL_RECURRING_CADENCE: "monthly",
                        quality.COL_RECURRING_CONFIDENCE: "high",
                        quality.COL_RECURRING_GROUP_KEY: "acc|merchant|monthly",
                        quality.COL_RECURRING_OCCURRENCE_COUNT: 4,
                    }
                ),
            ]
        )
    )

    assert report.passed is True
    assert quality.quality_check_report_to_dict(report) == {
        "passed": True,
        "finding_count": 0,
        "error_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "findings": [],
    }


def test_quality_checks_report_errors_and_warnings_for_bad_processed_rows() -> None:
    bad_rows = pd.DataFrame(
        [
            _quality_row(
                **{
                    quality.COL_TRANSACTION_ID: "txn-dup",
                    quality.COL_DIRECTION: "sideways",
                    quality.COL_CATEGORY_MAPPED: "luxury",
                    quality.COL_SUBCATEGORY_MAPPED: "unknown_subcategory",
                    quality.COL_RECURRING_CADENCE: "yearly",
                    quality.COL_RECURRING_CONFIDENCE: "certain",
                    quality.COL_AMOUNT: "not-a-number",
                    quality.COL_TIMESTAMP: "not-a-date",
                }
            ),
            _quality_row(
                **{
                    quality.COL_TRANSACTION_ID: "txn-dup",
                    quality.COL_AMOUNT: 0,
                    quality.COL_TIMESTAMP: "2999-01-01T00:00:00Z",
                    quality.COL_IS_RECURRING: True,
                    quality.COL_RECURRING_GROUP_KEY: "",
                    quality.COL_RECURRING_OCCURRENCE_COUNT: 1,
                }
            ),
            _quality_row(
                **{
                    quality.COL_TRANSACTION_ID: "txn-inconsistent",
                    quality.COL_RECURRING_CADENCE: "monthly",
                    quality.COL_RECURRING_CONFIDENCE: "medium",
                }
            ),
        ]
    )

    report = quality.run_quality_checks(bad_rows)
    serialized = quality.quality_check_report_to_dict(report)
    check_names = {finding["check_name"] for finding in serialized["findings"]}

    assert report.passed is False
    assert serialized["error_count"] >= 7
    assert serialized["warning_count"] >= 2
    assert quality.CHECK_DUPLICATE_TRANSACTION_IDS in check_names
    assert quality.CHECK_INVALID_DIRECTIONS in check_names
    assert quality.CHECK_INVALID_CATEGORIES in check_names
    assert quality.CHECK_INVALID_SUBCATEGORIES in check_names
    assert quality.CHECK_INVALID_RECURRENCE_CADENCE in check_names
    assert quality.CHECK_INVALID_RECURRENCE_CONFIDENCE in check_names
    assert quality.CHECK_IMPOSSIBLE_TIMESTAMPS in check_names
    assert quality.CHECK_IMPOSSIBLE_AMOUNTS in check_names
    assert quality.CHECK_RECURRING_FIELD_CONSISTENCY in check_names

    duplicate_finding = next(
        finding
        for finding in serialized["findings"]
        if finding["check_name"] == quality.CHECK_DUPLICATE_TRANSACTION_IDS
    )
    assert duplicate_finding["row_count"] == 2
    assert duplicate_finding["sample_ids"] == ["txn-dup", "txn-dup"]


def test_quality_checks_reject_missing_required_columns() -> None:
    with pytest.raises(quality.QualityCheckInputError):
        quality.run_quality_checks(pd.DataFrame({"transaction_id": ["txn-001"]}))
