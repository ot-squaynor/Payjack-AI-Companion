# PayJack AI – Data & Knowledge Base File & Folder Strategy

This document explains the **file and folder strategy** used for datasets and documentation in the PayJack AI repository.

The system separates information into two distinct layers:

| Layer | Folder | Purpose |
|------|------|------|
| **Knowledge Retrieval (RAG)** | `backend/kb/` | Documentation used by the LLM for answering informational questions |
| **Structured Data (Tools)** | `backend/data/` | Structured datasets queried directly by deterministic tools |

This separation ensures:

- PII and financial data are **never retrieved via RAG**
- Documentation retrieval remains **safe and explainable**
- Financial data queries remain **deterministic and auditable**

---

# 1. Knowledge Base (`backend/kb/`)

The **Knowledge Base** contains documentation that the AI retrieves using **RAG (Retrieval Augmented Generation)**.

Examples include:

- Help centre articles
- Product features
- Fees explanations
- Limits explanations
- Error explanations

These documents contain **no customer-specific information**.

---

# 1.1 KB Folder Structure
```
kb/
│
├── metadata/
│
├── processed_docs/
│
└── raw_docs/
├── errors/
├── features/
├── fees/
├── help_center/
└── limits/
```
---

# 1.2 `backend/kb/raw_docs/`

This folder contains the **original knowledge documents** before processing.

Documents here may come from:

- Help center exports
- Product documentation
- Policy documents
- Feature documentation
- Internal support documentation

Files in this folder are later **cleaned, chunked, and embedded** into the vector database.

---

# 1.3 KB Category Folders

## `backend/kb/raw_docs/help_center/`

Contains user support articles and FAQs.

Example structure:
```
help_center/
├── wallet/
├── card/
├── transfers/
└── account/
```
Example file:
```
help_center/transfers/how_to_send_money.md
```
Example Markdown:

```markdown
# How to Send Money

1. Open the PayJack app
2. Select Transfers
3. Enter recipient number
4. Confirm with PIN
```
---


## `backend/kb/raw_docs/fees/`

Contains explanations of product fees.

Example structure:
```
fees/
├── transfers/
├── card/
└── withdrawal/
```
Example Markdown:

```markdown
# Local Transfer Fees

Fee: GHS 2.50 per transfer

Notes:
Fees may vary depending on the product tier.
```
---

## `backend/kb/raw_docs/limits/`

Contains transaction and account limits.

Example structure:
```
limits/
├── transfers/
├── atm/
├── card/
└── wallet/
```
Example Markdown:

```markdown
# ATM Withdrawal Limits

Standard accounts: GHS 5,000/day  
Premium accounts: GHS 10,000/day
```
---

## `backend/kb/raw_docs/features/`

Contains product feature documentation.


Example structure:
```
features/
├── wallet/
├── transfers/
└── card/
```
Example Markdown:

```markdown
# Wallet Features

The PayJack wallet allows users to:

- Send money
- Pay merchants
- Receive transfers
```
---

## `backend/kb/raw_docs/errors/`

Contains explanations for common errors.

Example structure:
```
errors/
├── transfers/
├── authentication/
└── general/
```
Example Markdown:

```markdown
# Transfer Error: Transaction Failed

Possible causes:
- Network timeout
- Insufficient balance
- Recipient unavailable
```
---

# 1.4 Batch or Collected KB Files

Sometimes documentation may arrive as large exports rather than individual files.

Examples:
-Full Help Center export
-Policy document
-Product manual

Example:

```
backend/kb/raw_docs/help_center/help_center_full_export.md
```

The pipeline will later split these documents into smaller chunks during KB processing.

# 1.5 kb/processed_docs/

This folder stores cleaned and chunked versions of the documents used for embeddings.

Example:
```
processed_docs/
└── chunks.jsonl
```
Example chunk:
```
{"doc_id":"fees_transfer_local","chunk_id":0,"text":"Local transfer fee is GHS 2.50","metadata":{"type":"fees","product":"transfers"}}
```
These files are used to generate the vector database.

# 1.6 backend/kb/metadata/

Contains metadata about KB builds.

Example:
```
metadata/
└── kb_manifest.json
```
Example content:

```
{
  "build_id": "kb_build_2026_03_05",
  "documents": [
    "fees/transfers/local_transfer_fees.md",
    "help_center/transfers/how_to_send_money.md"
  ]
}
```
# 2. Structured Data (backend/data/)

The ```backend/data/``` directory contains structured datasets used by the assistant tools.

These datasets contain financial information and may contain sensitive data.

The AI does not retrieve these via RAG.

Instead they are queried through deterministic tools such as:

transaction_lookup

spend_summary

balances

# 2.1 Data Folder Structure
```
data/
│
├── embeddings/
├── mock/
├── processed/
└── raw/
    ├── accounts/
    ├── fees_and_limits/
    ├── metadata/
    ├── products/
    └── transactions/
```
# 2.2 backend/data/raw/

Contains original dataset exports from banking systems or APIs.

These may be:
-CSV exports
-JSON exports
-batch files

Example:

```raw/transactions/transactions_2026_03_05.csv```

# 2.3 backend/data/processed/

Contains standardized datasets created by the ingestion pipeline.

All files here follow the canonical dataset schema.

Example:

```processed/transactions.parquet``` 

```processed/accounts.parquet```

# 2.4 backend/data/raw/transactions/

Contains raw transaction exports.

-Example CSV:


| transaction_id | account_id | amount | currency | timestamp | merchant | category |
|---|---|---|---|---|---|---|
| txn_0001 | acc_001 | 125.75 | GHS | 2026-03-05T10:15:30Z | Melcom | groceries |
txn_0002 | acc_001 | 50.75 | GHS | 2026-03-05T10:15:30Z | Bolt | transport


-Example JSON:
```
[
  {
    "transaction_id": "txn_0001",
    "account_id": "acc_001",
    "amount": 125.75,
    "currency": "GHS",
    "timestamp": "2026-03-05T10:15:30Z",
    "merchant": "Melcom",
    "category": "groceries",
    "description": "Weekly groceries"
  }
]
```

-Example TXT:
```
transaction_id,account_id,amount,currency,timestamp,merchant,category,description
txn_0001,acc_001,125.75,GHS,2026-03-05T10:15:30Z,Melcom,groceries,Weekly groceries
txn_0002,acc_001,12.00,GHS,2026-03-05T15:01:00Z,Bolt,transport,Ride to work
```

-Example Markdown:

```markdown
#Transaction Record Example

## Transaction ID: txn_0001
Account ID: acc_001
Amount: 125.75 GHS
Timestamp: 2026-03-05T10:15:30Z

## Merchant: Melcom
Category: Groceries

##Description:
Weekly groceries
```

# 2.5 backend/data/raw/accounts/

Example CSV:
| account_id | account_name | account_type | currency |
|---|---|---|---|
| acc_001 | Main Account | current | GHS |
| acc_002 | Savings Account | savings | GHS |
| acc_003 | Business Account | business | GHS |

Example JSON:
```
[
  {
    "account_id": "acc_001",
    "account_name": "Main Account",
    "account_type": "current",
    "currency": "GHS"
  }
]
```
Example TXT:
```
account_id,account_name,account_type,currency
acc_001,Main Account,current,GHS
```

Example Markdown:

```markdown
# Account ID: acc_001

Account Name: Main Account
Account Type: Current
Currency: GHS

##Description:

Primary everyday account used for standard transactions and payments.
```
# 2.6 backend/data/raw/fees_and_limits/

Example CSV:
| item_id                | item_type | value | unit | notes              |
| ---------------------- | --------- | ----- | ---- | ------------------ |
| fee_transfer_local     | fee       | 2.5   | GHS  | Local transfer fee |
| limit_daily_withdrawal | limit     | 5000  | GHS  | Daily ATM limit    |

Example JSON:
```
[
{
"item_id": "fee_transfer_local",
"item_type": "fee",
"value": 2.5,
"unit": "GHS",
"notes": "Local transfer fee"
},
{
"item_id": "limit_daily_withdrawal",
"item_type": "limit",
"value": 5000,
"unit": "GHS",
"notes": "Daily ATM limit"
}
]
```
Example TXT:
```
fee_transfer_local | fee | 2.5 | GHS | Local transfer fee
limit_daily_withdrawal | limit | 5000 | GHS | Daily ATM limit
```
Example Markdown:

```markdown
# Fee and Limit Record Example
##Item ID: fee_transfer_local

Item Type: Fee
Value: 2.5 GHS

##Notes:

Local transfer fee applied to standard domestic transfers.
---
##Item ID: limit_daily_withdrawal

Item Type: Limit
Value: 5000 GHS

# Notes:

Maximum ATM withdrawal allowed per day.
```

# 2.7 backend/data/raw/products/
Example CSV
| product_id    | product_name      | product_type |
| ------------- | ----------------- | ------------ |
| prd_wallet    | PayJack Wallet    | wallet       |
| prd_card      | PayJack Card      | card         |
| prd_transfers | PayJack Transfers | transfers    |

Example JSON:
```
[
{
"product_id": "prd_wallet",
"product_name": "PayJack Wallet",
"product_type": "wallet"
},
{
"product_id": "prd_card",
"product_name": "PayJack Card",
"product_type": "card"
},
{
"product_id": "prd_transfers",
"product_name": "PayJack Transfers",
"product_type": "transfers"
}
]
```

Example TXT:
```
prd_wallet | PayJack Wallet | wallet
prd_card | PayJack Card | card
prd_transfers | PayJack Transfers | transfers
```
Example Markdown:

```markdown
# Product Record Example
## Product ID: prd_wallet

-Product Name: PayJack Wallet
-Product Type: Wallet

# Description:

Core wallet product used for storing funds, receiving money, and sending transfers.
```
# 2.9 backend/data/mock/


Contains synthetic datasets used for testing.

Example:
```
mock/
├── mock_transactions.json
├── mock_accounts.json
```
# 2.10 backend/data/embeddings/

Stores vector database persistence files.

Example:
```
embeddings/
└── chroma/
```
# 3. Summary
| Folder                      | Purpose                               |
|---------------------------|-------------------------------------|
| `backend/kb/raw_docs/`    | Source documents for RAG              |
| `backend/kb/processed_docs/` | Chunked documents used for embeddings |
| `backend/kb/metadata/`    | KB build metadata                     |
| `backend/data/raw/`       | Original dataset exports              |
| `backend/data/processed/` | Standardized datasets used by tools   |
| `backend/data/mock/`      | Synthetic datasets for testing        |
| `backend/data/embeddings/`| Vector database persistence           |

# Key Rule

KB = RAG retrieval (documentation)
DATA = deterministic tool queries (financial data)

This design ensures:

customer data stays secure

retrieval remains accurate

tool outputs remain deterministic

the AI does not hallucinate financial data