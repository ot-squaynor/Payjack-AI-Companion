from app.tools.recurring_detection import (
    detect_recurring_payments,
    normalize_recurring_detection_request,
    recurring_detection_result_to_dict,
)


def test_recurring_detection_filters_by_min_average_amount(sample_transactions_df) -> None:
    request = normalize_recurring_detection_request(
        min_average_amount="50",
        account_ids=["acc-001", "acc-002"],
    )

    result = recurring_detection_result_to_dict(
        detect_recurring_payments(sample_transactions_df, request)
    )

    assert result["match_count"] == 1
    assert result["records"][0]["account_id"] == "acc-002"
    assert result["records"][0]["average_amount"] == "99.99"
    assert result["applied_filters"]["min_average_amount"] == "50.00"
