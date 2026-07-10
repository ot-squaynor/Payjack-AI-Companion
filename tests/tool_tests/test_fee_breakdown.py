import pandas as pd

from app.tools.fee_breakdown import (
    breakdown_fees,
    fee_breakdown_result_to_dict,
    normalize_fee_breakdown_request,
)


def test_fee_breakdown_detects_fee_like_transactions() -> None:
    df = pd.DataFrame(
        [
            {
                "transaction_id": "txn-fee-001",
                "account_id": "acc-001",
                "timestamp": "2026-03-21T10:00:00Z",
                "amount": 2.50,
                "currency": "GHS",
                "direction": "debit",
                "merchant": "PayJack Service Fee",
                "category": "fees",
                "subcategory": "transfer_fee",
            },
            {
                "transaction_id": "txn-regular-001",
                "account_id": "acc-001",
                "timestamp": "2026-03-20T10:00:00Z",
                "amount": 45.00,
                "currency": "GHS",
                "direction": "debit",
                "merchant": "Fresh Market",
                "category": "groceries",
                "subcategory": "food",
            },
        ]
    )

    result = breakdown_fees(
        df,
        normalize_fee_breakdown_request(
            user_id="user-123",
            account_ids=("acc-001",),
            start_date="2026-03-01",
            end_date="2026-03-31",
        ),
    )
    payload = fee_breakdown_result_to_dict(result)

    assert payload["transaction_count"] == 1
    assert payload["total_amount"] == "2.50"
    assert payload["records"][0]["transaction_id"] == "txn-fee-001"
    assert payload["records"][0]["matched_reason"] in {
        "category_matched_fee_term",
        "subcategory_matched_fee_term",
        "merchant_matched_fee_term",
    }


def test_fee_breakdown_returns_warning_when_no_fees_match() -> None:
    df = pd.DataFrame(
        [
            {
                "transaction_id": "txn-regular-001",
                "account_id": "acc-001",
                "timestamp": "2026-03-20T10:00:00Z",
                "amount": 45.00,
                "currency": "GHS",
                "direction": "debit",
                "merchant": "Fresh Market",
                "category": "groceries",
                "subcategory": "food",
            }
        ]
    )

    result = breakdown_fees(df, normalize_fee_breakdown_request(account_ids=("acc-001",)))

    assert result.records == ()
    assert result.warnings == ("No fee-like transactions matched the provided filters.",)
