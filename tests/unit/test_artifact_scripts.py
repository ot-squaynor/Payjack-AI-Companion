import json
from pathlib import Path
import re
import shutil
from types import SimpleNamespace

import pandas as pd
import pytest

from app.data_pipeline.processed_schema import (
    PROCESSED_ARTIFACT_MANIFEST_FILENAME,
    QualityCheckSummary,
    build_dataset_artifact,
)
from scripts import dataset_transform
from scripts import embeddings_generate
from scripts import kb_build
from scripts import kb_publish


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", request.node.name)
    path = (
        Path(__file__).resolve().parents[2]
        / ".pytest_runtime_assets"
        / "artifact_scripts"
        / safe_name
    )
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def _dataset_args(**overrides: object) -> SimpleNamespace:
    defaults = {
        "source_mode": "local",
        "local_root": "data/raw",
        "raw_bucket": None,
        "raw_prefix": "",
        "transactions_bucket": None,
        "transactions_prefix": "",
        "accounts_bucket": None,
        "accounts_prefix": "",
        "fees_bucket": None,
        "fees_prefix": "",
        "products_bucket": None,
        "products_prefix": "",
        "metadata_bucket": None,
        "metadata_prefix": "",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_dataset_transform_resolves_local_and_s3_sources(tmp_path: Path) -> None:
    local_config = dataset_transform._resolve_source_config(
        "transactions",
        _dataset_args(local_root=str(tmp_path)),
    )
    assert local_config is not None
    assert local_config.mode == "local"
    assert local_config.local_root == tmp_path

    s3_config = dataset_transform._resolve_source_config(
        "transactions",
        _dataset_args(
            source_mode="s3",
            raw_bucket="raw-bucket",
            raw_prefix="raw-prefix",
            transactions_bucket="transactions-bucket",
            transactions_prefix="transactions-prefix",
        ),
    )
    assert s3_config is not None
    assert s3_config.mode == "s3"
    assert s3_config.s3_bucket == "transactions-bucket"
    assert s3_config.s3_root_prefix == "transactions-prefix"

    assert (
        dataset_transform._resolve_source_config(
            "transactions",
            _dataset_args(source_mode="s3"),
        )
        is None
    )


def test_dataset_transform_load_bundle_requires_transactions_and_skips_optional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = {"transactions": object(), "accounts": object()}
    calls: list[str] = []

    def fake_ingest_dataset(*, spec: object, source_config: object) -> pd.DataFrame:
        dataset_name = next(name for name, value in specs.items() if value is spec)
        calls.append(dataset_name)
        if dataset_name == "accounts":
            raise dataset_transform.ingestion.IngestionError("optional source missing")
        return pd.DataFrame({"transaction_id": ["txn-001"]})

    monkeypatch.setattr(dataset_transform.ingestion, "_specs", lambda: specs)
    monkeypatch.setattr(
        dataset_transform.ingestion,
        "ingest_dataset",
        fake_ingest_dataset,
    )

    bundle = dataset_transform._load_bundle(_dataset_args())

    assert calls == ["transactions", "accounts"]
    assert list(bundle) == ["transactions"]
    assert bundle["transactions"].iloc[0]["transaction_id"] == "txn-001"


def test_dataset_transform_prepares_and_finalizes_transactions() -> None:
    prepared = dataset_transform._prepare_transactions_for_mapping(
        pd.DataFrame(
            [
                {
                    "transaction_id": "txn-001",
                    "merchant_clean": " Melcom GH ",
                    "category": " Groceries ",
                }
            ]
        )
    )
    assert prepared.loc[0, "merchant_normalized"] == "melcom gh"
    assert prepared.loc[0, "category_normalized"] == "groceries"

    finalized = dataset_transform._finalize_transactions(
        pd.DataFrame(
            [
                {
                    "merchant": "Original Merchant",
                    "merchant_clean": "Clean Merchant",
                    "merchant_mapped": "",
                    "category_mapped": "groceries",
                    "subcategory_mapped": "supermarket",
                    "amount": "-12.50",
                },
                {
                    "merchant": "Original Merchant",
                    "merchant_clean": None,
                    "merchant_mapped": "melcom",
                    "category_mapped": "groceries",
                    "subcategory_mapped": "supermarket",
                    "amount": "-10",
                },
            ]
        )
    )

    assert finalized["merchant"].tolist() == ["Clean Merchant", "melcom"]
    assert finalized["merchant_clean"].tolist() == ["Clean Merchant", "melcom"]
    assert finalized["category"].tolist() == ["groceries", "groceries"]
    assert finalized["subcategory"].tolist() == ["supermarket", "supermarket"]
    assert finalized["amount"].tolist() == [12.5, 10.0]


class _FakeS3Client:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, str, dict[str, str] | None]] = []

    def upload_file(
        self,
        filename: str,
        bucket: str,
        key: str,
        ExtraArgs: dict[str, str] | None = None,
    ) -> None:
        self.uploads.append((Path(filename).name, bucket, key, ExtraArgs))


def test_dataset_transform_upload_outputs_adds_s3_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "transactions.parquet").write_text("data", encoding="utf-8")
    (tmp_path / "qc_report.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pipeline_summary.json").write_text("{}", encoding="utf-8")
    (tmp_path / PROCESSED_ARTIFACT_MANIFEST_FILENAME).write_text(
        "{}",
        encoding="utf-8",
    )
    fake_client = _FakeS3Client()
    monkeypatch.setattr(dataset_transform.boto3, "client", lambda service: fake_client)
    manifest = dataset_transform.ProcessedArtifactManifest(
        schema_version="1",
        dataset_version="v1",
        build_id="build-1",
        environment="test",
        source_mode="local",
        created_at="2026-01-01T00:00:00Z",
        artifacts={
            "transactions": build_dataset_artifact(
                name="transactions",
                filename="transactions.parquet",
                row_count=1,
                columns=["transaction_id"],
                local_path=str(tmp_path / "transactions.parquet"),
            )
        },
        qc_summary=QualityCheckSummary(
            passed=True,
            finding_count=0,
            error_count=0,
            warning_count=0,
            info_count=0,
        ),
    )

    updated_manifest = dataset_transform._upload_outputs_to_s3(
        output_dir=tmp_path,
        manifest=manifest,
        output_bucket="processed-bucket",
        output_prefix="processed/local",
        expected_bucket_owner="123456789012",
    )

    assert updated_manifest.artifacts["transactions"].s3_key == (
        "processed/local/transactions.parquet"
    )
    assert fake_client.uploads == [
        (
            "transactions.parquet",
            "processed-bucket",
            "processed/local/transactions.parquet",
            {"ExpectedBucketOwner": "123456789012"},
        ),
        (
            "qc_report.json",
            "processed-bucket",
            "processed/local/qc_report.json",
            {"ExpectedBucketOwner": "123456789012"},
        ),
        (
            "pipeline_summary.json",
            "processed-bucket",
            "processed/local/pipeline_summary.json",
            {"ExpectedBucketOwner": "123456789012"},
        ),
        (
            PROCESSED_ARTIFACT_MANIFEST_FILENAME,
            "processed-bucket",
            f"processed/local/{PROCESSED_ARTIFACT_MANIFEST_FILENAME}",
            {"ExpectedBucketOwner": "123456789012"},
        ),
    ]


def test_dataset_transform_resolves_expected_bucket_owner_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("S3_EXPECTED_BUCKET_OWNER", raising=False)
    monkeypatch.setenv("AWS_ACCOUNT_ID", "111122223333")

    assert dataset_transform._resolve_expected_bucket_owner() == "111122223333"

    monkeypatch.setenv("S3_EXPECTED_BUCKET_OWNER", "444455556666")

    assert dataset_transform._resolve_expected_bucket_owner() == "444455556666"
    assert dataset_transform._resolve_expected_bucket_owner("777788889999") == (
        "777788889999"
    )


def test_kb_build_main_writes_chunks_and_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "raw_docs"
    output_dir = tmp_path / "processed_docs"
    metadata_dir = tmp_path / "metadata"
    (input_dir / "policies").mkdir(parents=True)
    (input_dir / "policies" / "card_limits.txt").write_text(
        "Card limits",
        encoding="utf-8",
    )
    (input_dir / "policies" / "ignore.bin").write_text("skip", encoding="utf-8")

    monkeypatch.setattr(
        kb_build,
        "parse_args",
        lambda: SimpleNamespace(
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            metadata_dir=str(metadata_dir),
            chunk_size=1000,
            chunk_overlap=200,
            log_level="INFO",
        ),
    )
    monkeypatch.setattr(
        kb_build,
        "load_file_chunks",
        lambda path, **kwargs: [
            {
                "doc_id": kwargs["doc_id"],
                "chunk_id": f'{kwargs["doc_id"]}:0',
                "text": path.read_text(encoding="utf-8"),
            }
        ],
    )

    kb_build.main()

    chunks = [
        json.loads(line)
        for line in (output_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    manifest = json.loads(
        (metadata_dir / "kb_manifest.json").read_text(encoding="utf-8")
    )

    assert chunks == [
        {
            "doc_id": "policies_card_limits_txt",
            "chunk_id": "policies_card_limits_txt:0",
            "text": "Card limits",
        }
    ]
    assert manifest["documents"] == ["policies/card_limits.txt"]
    assert manifest["chunk_count"] == 1


def test_embeddings_generate_main_writes_deterministic_token_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunks_path = tmp_path / "chunks.jsonl"
    output_path = tmp_path / "embeddings.jsonl"
    chunks_path.write_text(
        json.dumps(
            {
                "doc_id": "doc-1",
                "chunk_id": "chunk-1",
                "text": "Beta alpha beta",
            }
        )
        + "\n\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        embeddings_generate,
        "parse_args",
        lambda: SimpleNamespace(
            chunks_path=str(chunks_path),
            output_path=str(output_path),
            log_level="INFO",
        ),
    )

    embeddings_generate.main()

    rows = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    assert rows == [
        {
            "doc_id": "doc-1",
            "chunk_id": "chunk-1",
            "token_hashes": embeddings_generate._token_hashes("Beta alpha beta"),
        }
    ]
    assert embeddings_generate._token_hashes("beta alpha") == (
        embeddings_generate._token_hashes("alpha beta beta")
    )


def test_kb_publish_upload_directory_uses_prefix_and_skips_directories(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "processed"
    nested_dir = source_dir / "nested"
    nested_dir.mkdir(parents=True)
    (source_dir / "chunks.jsonl").write_text("{}", encoding="utf-8")
    (nested_dir / "metadata.json").write_text("{}", encoding="utf-8")
    fake_client = _FakeS3Client()

    kb_publish._upload_directory(
        fake_client,
        bucket="kb-bucket",
        prefix="kb/processed_docs",
        directory=source_dir,
    )

    assert fake_client.uploads == [
        ("chunks.jsonl", "kb-bucket", "kb/processed_docs/chunks.jsonl", None),
        (
            "metadata.json",
            "kb-bucket",
            "kb/processed_docs/nested/metadata.json",
            None,
        ),
    ]
