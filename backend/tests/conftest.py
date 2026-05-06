# backend/tests/conftest.py
# 2026-04-02
"""Purpose: Provide shared backend fixtures for local runtime, repository, and API tests."""

from __future__ import annotations

##BRICK 1: Imports, path bootstrap, and shared env loading
import importlib
import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.data_pipeline.processed_schema import (
    PROCESSED_ARTIFACT_SCHEMA_VERSION,
    ProcessedArtifactManifest,
    build_dataset_artifact,
    build_qc_summary,
    write_manifest,
)
from app.env import load_local_env


load_local_env()


##BRICK 2: Synthetic processed dataset fixtures
@pytest.fixture
def sample_transactions_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "transaction_id": "txn-001",
                "account_id": "acc-001",
                "timestamp": "2026-03-28T10:00:00Z",
                "amount": 45.50,
                "currency": "GHS",
                "direction": "debit",
                "merchant": "Fresh Market",
                "category": "groceries",
                "subcategory": "food",
                "status": "posted",
                "is_recurring": False,
                "recurrence_cadence": "irregular",
                "recurrence_confidence": "low",
            },
            {
                "transaction_id": "txn-002",
                "account_id": "acc-001",
                "timestamp": "2026-03-20T09:15:00Z",
                "amount": 25.00,
                "currency": "GHS",
                "direction": "debit",
                "merchant": "Fuel Station",
                "category": "transport",
                "subcategory": "fuel",
                "status": "pending",
                "is_recurring": True,
                "recurrence_cadence": "monthly",
                "recurrence_confidence": "high",
            },
            {
                "transaction_id": "txn-003",
                "account_id": "acc-002",
                "timestamp": "2026-03-15T18:45:00Z",
                "amount": 99.99,
                "currency": "GHS",
                "direction": "debit",
                "merchant": "Utility Co",
                "category": "bills",
                "subcategory": "utilities",
                "status": "posted",
                "is_recurring": True,
                "recurrence_cadence": "monthly",
                "recurrence_confidence": "medium",
            },
            {
                "transaction_id": "txn-004",
                "account_id": "acc-001",
                "timestamp": "2026-03-10T08:30:00Z",
                "amount": 2.50,
                "currency": "GHS",
                "direction": "debit",
                "merchant": "PayJack Service Fee",
                "category": "fees",
                "subcategory": "transfer_fee",
                "status": "posted",
                "is_recurring": False,
                "recurrence_cadence": "irregular",
                "recurrence_confidence": "low",
            },
        ]
    )


@pytest.fixture
def sample_accounts_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "account_id": "acc-001",
                "account_name": "Main Wallet",
                "currency": "GHS",
                "current_balance": 1200.50,
                "available_balance": 1180.50,
            },
            {
                "account_id": "acc-002",
                "account_name": "Savings Pocket",
                "currency": "GHS",
                "current_balance": 500.00,
                "available_balance": 500.00,
            },
        ]
    )


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


def _runtime_assets_root() -> Path:
    root = BACKEND_ROOT / "tests" / "runtime_assets"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def processed_test_assets(
    sample_transactions_df: pd.DataFrame,
    sample_accounts_df: pd.DataFrame,
) -> dict[str, Path]:
    runtime_root = _runtime_assets_root()
    processed_root = runtime_root / "processed"
    processed_root.mkdir(parents=True, exist_ok=True)

    transactions_path = processed_root / "transactions.jsonl"
    accounts_path = processed_root / "accounts.jsonl"
    _write_jsonl(transactions_path, sample_transactions_df.to_dict(orient="records"))
    _write_jsonl(accounts_path, sample_accounts_df.to_dict(orient="records"))

    manifest = ProcessedArtifactManifest(
        schema_version=PROCESSED_ARTIFACT_SCHEMA_VERSION,
        dataset_version="test-dataset-2026-04-02",
        build_id="test-build-001",
        environment="test",
        source_mode="local",
        created_at="2026-04-02T12:00:00Z",
        artifacts={
            "transactions": build_dataset_artifact(
                name="transactions",
                filename=transactions_path.name,
                row_count=len(sample_transactions_df),
                columns=list(sample_transactions_df.columns),
                local_path=str(transactions_path),
            ),
            "accounts": build_dataset_artifact(
                name="accounts",
                filename=accounts_path.name,
                row_count=len(sample_accounts_df),
                columns=list(sample_accounts_df.columns),
                local_path=str(accounts_path),
            ),
        },
        qc_summary=build_qc_summary(
            {
                "passed": True,
                "finding_count": 0,
                "error_count": 0,
                "warning_count": 0,
                "info_count": 0,
            }
        ),
    )
    write_manifest(manifest, processed_root)

    kb_root = runtime_root / "kb"
    kb_root.mkdir(parents=True, exist_ok=True)
    kb_chunks_path = kb_root / "chunks.jsonl"
    kb_chunks = [
        {
            "doc_id": "fees_policy",
            "chunk_id": 0,
            "title": "Fees Policy",
            "text": "Payjack fee explanations are available in the help center.",
            "metadata": {"type": "policy", "source_path": "policies/fees.md"},
        },
        {
            "doc_id": "jackinvest_overview",
            "chunk_id": 0,
            "title": "JackInvest Overview",
            "text": "JackInvest is a Payjack product area for investment education, product information, fees, and risk explanations.",
            "metadata": {"type": "product", "source_path": "products/jackinvest.md"},
        },
        {
            "doc_id": "payjack_limits",
            "chunk_id": 0,
            "title": "Payjack Transfer Limits",
            "text": "Payjack transfer limits and app usage guidance are documented in the help center.",
            "metadata": {"type": "policy", "source_path": "policies/limits.md"},
        },
        {
            "doc_id": "onboarding_help",
            "chunk_id": 0,
            "title": "Onboarding Help",
            "text": "Payjack onboarding guides explain verification, KYC, app setup, and common onboarding errors.",
            "metadata": {"type": "help", "source_path": "help/onboarding.md"},
        },
    ]
    kb_chunks_path.write_text(
        "\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in kb_chunks) + "\n",
        encoding="utf-8",
    )

    return {
        "runtime_root": runtime_root,
        "processed_root": processed_root,
        "kb_chunks_path": kb_chunks_path,
    }


##BRICK 3: Test environment and API client fixtures
@pytest.fixture
def configured_test_env(
    monkeypatch: pytest.MonkeyPatch,
    processed_test_assets: dict[str, Path],
) -> dict[str, Path]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("PROCESSED_STORE_MODE", "local")
    monkeypatch.setenv("PROCESSED_LOCAL_ROOT", str(processed_test_assets["processed_root"]))
    monkeypatch.setenv("USE_MOCK_BEDROCK", "true")
    monkeypatch.setenv("USE_LOCAL_RAG", "true")
    monkeypatch.setenv("ENABLE_DEBUG_TRACES", "true")
    monkeypatch.setenv("KB_CHUNKS_PATH", str(processed_test_assets["kb_chunks_path"]))
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    return processed_test_assets


@pytest.fixture
def test_client(configured_test_env: dict[str, Path]) -> TestClient:
    import app.main as main_module

    importlib.reload(main_module)
    with TestClient(main_module.create_app()) as client:
        yield client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {
        "x-payjack-user-id": "user-123",
        "x-payjack-tenant-id": "tenant-001",
        "x-payjack-roles": "customer",
        "x-payjack-account-ids": "acc-001",
    }
