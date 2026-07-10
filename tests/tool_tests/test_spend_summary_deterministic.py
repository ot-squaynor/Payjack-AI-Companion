from app.tools.spend_summary import (
    normalize_spend_summary_request,
    spend_summary_result_to_dict,
    summarize_spend,
)


def test_spend_summary_is_deterministic(sample_transactions_df) -> None:
    request = normalize_spend_summary_request(
        categories=["groceries", "transport"],
        direction="debit",
        group_by="category",
        limit=10,
    )

    first = spend_summary_result_to_dict(summarize_spend(sample_transactions_df, request))
    second = spend_summary_result_to_dict(summarize_spend(sample_transactions_df, request))

    assert first == second
    assert first["total_amount"] == "70.50"
    assert first["transaction_count"] == 2
    assert first["grouped_breakdown"][0]["key"] == "groceries"
