import pandas as pd

from app.data_pipeline.ingestion import _adapt_payjack_transfer_export, _specs, standardize_columns


def test_adapts_local_payjack_transfer_export() -> None:
    df = standardize_columns(
        pd.DataFrame(
            [
                {
                    "actorId": 1141,
                    "firstName": "Blake",
                    "lastName": "Gibson",
                    "transactionType": "P2P",
                    "transferAmount": 75.25,
                    "transferDateTime": "2022-12-22T05:20:34.297",
                    "_source_name": "aidata2.json",
                }
            ]
        )
    )

    adapted_df = _adapt_payjack_transfer_export(df, _specs()["transactions"])

    row = adapted_df.iloc[0]
    assert str(row["account_id"]) == "1141"
    assert row["amount"] == -75.25
    assert row["currency"] == "GHS"
    assert row["merchant"] == "P2P"
    assert row["category"] == "P2P"
    assert row["transaction_id"].startswith("txn-")
